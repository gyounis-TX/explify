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
    const subscriptionId = body.subscription_id;

    if (!subscriptionId) {
      return new Response(
        JSON.stringify({ error: "subscription_id required" }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }

    // Verify the subscription belongs to this user
    const { data: sub } = await supabase
      .from("subscriptions")
      .select("user_id")
      .eq("id", subscriptionId)
      .maybeSingle();

    if (!sub || sub.user_id !== user.id) {
      return new Response(
        JSON.stringify({ error: "Subscription not found or unauthorized" }),
        {
          status: 403,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }

    // Check for retention offer
    const { data: retentionConfig } = await supabase
      .from("billing_config")
      .select("value")
      .eq("key", "retention_coupon_id")
      .maybeSingle();

    const retentionCouponId = retentionConfig?.value;

    if (retentionCouponId && !body.accept_retention) {
      // Check if we've already offered retention
      const { data: pastCancellations } = await supabase
        .from("subscription_cancellations")
        .select("id")
        .eq("user_id", user.id)
        .eq("retention_offered", true)
        .limit(1);

      if (!pastCancellations || pastCancellations.length === 0) {
        // Get retention offer text
        const { data: offerText } = await supabase
          .from("billing_config")
          .select("value")
          .eq("key", "retention_offer_text")
          .maybeSingle();

        // Record that we offered retention
        await supabase.from("subscription_cancellations").insert({
          user_id: user.id,
          subscription_id: subscriptionId,
          reason: body.reason || "",
          reason_detail: body.reason_detail || "",
          retention_offered: true,
          retention_accepted: false,
        });

        return new Response(
          JSON.stringify({
            retention_offer: {
              coupon_id: retentionCouponId,
              text: offerText?.value || "Stay for a special discount!",
            },
          }),
          {
            status: 200,
            headers: { ...corsHeaders, "Content-Type": "application/json" },
          },
        );
      }
    }

    // Cancel at end of period
    await stripe.subscriptions.update(subscriptionId, {
      cancel_at_period_end: true,
    });

    // Update local record
    await supabase
      .from("subscriptions")
      .update({
        cancel_at_period_end: true,
        canceled_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq("id", subscriptionId);

    return new Response(
      JSON.stringify({ canceled: true, cancel_at_period_end: true }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  } catch (err) {
    console.error("cancel-subscription error:", err);
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : "Unknown error" }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }
});
