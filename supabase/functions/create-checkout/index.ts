import Stripe from "https://esm.sh/stripe@14.14.0?target=deno";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";

const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY")!, {
  apiVersion: "2024-04-10",
  httpClient: Stripe.createFetchHttpClient(),
});

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  try {
    // Verify JWT
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) {
      return new Response(JSON.stringify({ error: "Missing authorization" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const { data: { user }, error: authError } = await supabase.auth.getUser(
      authHeader.replace("Bearer ", ""),
    );
    if (authError || !user) {
      return new Response(JSON.stringify({ error: "Invalid token" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const body = await req.json();
    const tier = body.tier || "starter";
    const successUrl = body.success_url || "";
    const cancelUrl = body.cancel_url || "";

    // Look up or create Stripe customer
    let stripeCustomerId: string;
    const { data: existingCustomer } = await supabase
      .from("customers")
      .select("stripe_customer_id")
      .eq("user_id", user.id)
      .maybeSingle();

    if (existingCustomer) {
      stripeCustomerId = existingCustomer.stripe_customer_id;
    } else {
      const customer = await stripe.customers.create({
        email: user.email,
        metadata: { user_id: user.id },
      });
      stripeCustomerId = customer.id;
      await supabase.from("customers").insert({
        user_id: user.id,
        stripe_customer_id: customer.id,
      });
    }

    // Look up price for the tier
    const { data: price } = await supabase
      .from("prices")
      .select("id")
      .eq("tier", tier)
      .eq("interval", "month")
      .eq("active", true)
      .maybeSingle();

    if (!price) {
      return new Response(
        JSON.stringify({ error: `No active price found for tier: ${tier}` }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }

    // Get trial period from config
    const { data: trialConfig } = await supabase
      .from("billing_config")
      .select("value")
      .eq("key", "trial_period_days")
      .maybeSingle();

    const trialDays = trialConfig ? parseInt(trialConfig.value, 10) : 14;

    // Check if user has had a subscription before (no trial for returning users)
    const { data: pastSubs } = await supabase
      .from("subscriptions")
      .select("id")
      .eq("user_id", user.id)
      .limit(1);

    const isFirstTime = !pastSubs || pastSubs.length === 0;

    const sessionParams: Stripe.Checkout.SessionCreateParams = {
      customer: stripeCustomerId,
      mode: "subscription",
      line_items: [{ price: price.id, quantity: 1 }],
      success_url: successUrl || undefined,
      cancel_url: cancelUrl || undefined,
      metadata: { user_id: user.id, tier },
      client_reference_id: user.id,
    };

    if (isFirstTime && trialDays > 0) {
      sessionParams.subscription_data = {
        trial_period_days: trialDays,
        metadata: { tier },
      };
    }

    const session = await stripe.checkout.sessions.create(sessionParams);

    return new Response(JSON.stringify({ url: session.url }), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("create-checkout error:", err);
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : "Unknown error" }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }
});
