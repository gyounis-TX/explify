# Privacy Policy

**Effective Date:** [DATE]

**Last Updated:** [DATE]

This Privacy Policy describes how [YOUR LEGAL ENTITY NAME] ("Company," "we," "us," or "our") collects, uses, stores, and protects information when you use Explify ("Service") at explify.app or through our desktop application.

By using the Service, you agree to the collection and use of information in accordance with this Privacy Policy.

---

## 1. Information We Collect

### 1.1 Account Information

When you create an account, we collect:

- **Email address** (used for authentication, account recovery, and communication)
- **Password** (hashed; we never store or have access to your plaintext password)
- **Authentication provider data** (if you sign in with Google: your Google account email and profile name)

### 1.2 Medical Report Content

When you use the Service, you may submit medical report text by:

- Uploading PDF or image files
- Pasting text directly into the application
- Importing from device storage

This content may contain Protected Health Information (PHI), including patient names, dates of birth, medical record numbers, and test results. See Section 4 for how we handle this data.

### 1.3 Generated Content

The Service creates and stores the following content in your account:

- AI-generated report explanations and summaries
- Key findings and measurement extractions
- Patient-friendly letters
- Teaching points and templates you create
- Report comparison and synthesis results

### 1.4 Usage Data

We collect information about how you use the Service:

- **Feature usage**: which features you use and how often (e.g., report count, letter count, batch processing)
- **AI model usage**: which AI model was used, input/output token counts (for cost tracking and tier enforcement)
- **Session data**: login timestamps, session duration
- **Error data**: application errors and stack traces (via Sentry; see Section 3.5 — no medical content is included)

### 1.5 Billing Data

If you subscribe to a paid plan, Stripe collects and processes:

- Credit/debit card number, expiration, and CVC
- Billing name and address
- PayPal or Apple Pay account details (if used)

**We do not store your payment card details.** All payment data is handled directly by Stripe. We only store your Stripe customer ID, subscription status, and billing period dates.

### 1.6 Settings and Preferences

We store your application settings, including:

- Medical specialty, literacy level, and tone preferences
- Custom templates and output formatting preferences
- Onboarding and consent completion status
- Display preferences

### 1.7 Information We Do NOT Collect

- We do not use cookies for advertising or third-party tracking.
- We do not collect precise geolocation data.
- We do not access your device contacts, camera, or microphone.
- We do not scan or access files on your device beyond those you explicitly import.

---

## 2. How We Use Your Information

We use the information we collect to:

| Purpose | Data Used |
|---------|-----------|
| Provide the Service (generate explanations) | Medical report text, settings |
| Authenticate your identity | Email, password, OAuth tokens |
| Store your report history and content | Generated content, metadata |
| Process subscription payments | Stripe customer ID, plan details |
| Enforce subscription tier limits | Usage counts, tier assignment |
| Send transactional emails | Email address |
| Monitor and fix errors | Error logs, stack traces (no PHI) |
| Improve the Service | Aggregated, anonymized usage statistics |
| Respond to support requests | Email, account information |
| Comply with legal obligations | Account and billing records |

**We do not sell your personal information. We do not use your medical report content to train AI models.**

---

## 3. Third-Party Data Processors

We use the following third-party services to operate the Service. Each processes data only as necessary to perform its function:

### 3.1 Supabase (Authentication & Database)

- **What they process**: Account information, settings, report history, generated content, usage data
- **Where**: Hosted on AWS in the United States
- **Retention**: Data persists until you delete it or delete your account
- **Their policy**: [supabase.com/privacy](https://supabase.com/privacy)

### 3.2 Anthropic (AI Processing — Claude Models)

- **What they process**: Medical report text submitted for explanation (sent as API request)
- **Data retention**: Anthropic does not retain API inputs or outputs beyond the request lifecycle for commercial API usage. They do not use API data to train models.
- **Where**: United States
- **Their policy**: [anthropic.com/privacy](https://www.anthropic.com/privacy)
- **Their usage policy**: [anthropic.com/api-usage-policy](https://docs.anthropic.com/en/docs/usage-policy)

### 3.3 Amazon Web Services — Bedrock (AI Processing)

- **What they process**: Medical report text submitted for explanation (sent as API request via AWS Bedrock)
- **Data retention**: AWS Bedrock does not store or use customer inputs/outputs for model training.
- **Where**: United States (us-east-1 region)
- **Their policy**: [aws.amazon.com/privacy](https://aws.amazon.com/privacy/)
- **Bedrock data privacy**: [docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html](https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html)

### 3.4 OpenAI (AI Processing — if configured by user)

- **What they process**: Medical report text submitted for explanation (sent as API request)
- **Data retention**: OpenAI's API does not use inputs/outputs for model training. Data is retained for up to 30 days for abuse monitoring, then deleted.
- **Where**: United States
- **Their policy**: [openai.com/policies/privacy-policy](https://openai.com/policies/privacy-policy)
- **API data usage**: [openai.com/enterprise-privacy](https://openai.com/enterprise-privacy)

### 3.5 Sentry (Error Monitoring)

- **What they process**: Application error reports, stack traces, browser/device metadata
- **What they do NOT receive**: Medical report text, patient data, or any PHI. Our integration includes a `before_send` filter that strips request bodies and local variables before transmission.
- **Where**: United States
- **Their policy**: [sentry.io/privacy](https://sentry.io/privacy/)

### 3.6 Stripe (Payment Processing)

- **What they process**: Payment card details, billing address, subscription status, invoices
- **What they do NOT receive**: Medical report text, health data, or any PHI
- **Where**: United States
- **Their policy**: [stripe.com/privacy](https://stripe.com/privacy)

### 3.7 Resend (Transactional Email)

- **What they process**: Email address, email subject and body content
- **What they do NOT receive**: Medical report text or health data
- **Where**: United States
- **Their policy**: [resend.com/legal/privacy-policy](https://resend.com/legal/privacy-policy)

---

## 4. Medical Data and PHI

### 4.1 How Medical Report Text Is Handled

When you submit a medical report:

1. **Upload/paste**: The report text is extracted on our servers (for web) or locally on your device (for desktop).
2. **Processing**: The extracted text is sent to the configured AI provider (Anthropic, AWS Bedrock, or OpenAI) via their commercial API for explanation generation.
3. **Storage**: The original report text, extracted data, and generated explanations are stored in your account database.
4. **Deletion**: You can delete any report from your history at any time. Deleted reports are permanently removed from our database.

### 4.2 PHI Scrubbing

The Service includes an optional PHI scrubbing feature that attempts to remove patient identifiers (names, dates of birth, medical record numbers, Social Security numbers) from report text before sending it to AI providers. This feature is best-effort and may not catch all identifiers.

### 4.3 HIPAA Notice

**Explify is not a HIPAA-covered entity.** The Service is designed for individuals to understand their own medical reports. We do not enter into Business Associate Agreements (BAAs) with users. If you are a healthcare provider or organization subject to HIPAA and wish to use Explify in a clinical setting, please contact us to discuss compliance requirements.

### 4.4 Desktop Application

When using the desktop application, report processing occurs locally on your device. Report text is sent directly from your device to the AI provider using API keys you provide. In this mode, the Company's servers are not involved in processing your medical data.

---

## 5. Data Retention

| Data Type | Retention Period |
|-----------|-----------------|
| Account information | Until you delete your account |
| Medical report content and explanations | Until you delete individual reports or your account |
| Settings and preferences | Until you delete your account |
| Usage logs | 12 months from creation |
| Billing records | 7 years (legal/tax requirement) |
| Error logs (Sentry) | 90 days |
| Transactional email records | 30 days |

---

## 6. Your Rights

### 6.1 Access and Portability

You have the right to access and export all personal data we hold about you. Use the **Export My Data** feature in Settings to download a complete copy of your data in JSON format.

### 6.2 Deletion

You have the right to delete your account and all associated data. Use the **Delete My Account** feature in Settings. This will:

- Permanently delete all your data from our database (settings, history, templates, letters, teaching points, usage logs)
- Cancel any active subscription
- Remove your authentication account

Deletion is permanent and cannot be undone.

### 6.3 Correction

You can update your account information (email, password) through the Service at any time. You can edit or delete individual reports, templates, and letters.

### 6.4 Objection and Restriction

If you wish to restrict or object to specific processing activities, contact us at [SUPPORT EMAIL]. Note that restricting core processing may prevent us from providing the Service.

### 6.5 Exercising Your Rights

To exercise any of these rights, you may:

- Use the self-service features in the application (export, delete, edit)
- Contact us at [SUPPORT EMAIL]

We will respond to requests within 30 days. We may ask you to verify your identity before processing a request.

---

## 7. Data Security

We implement the following measures to protect your data:

- **Encryption in transit**: All data transmitted between your device, our servers, and third-party services uses TLS 1.2 or higher.
- **Encryption at rest**: Database storage is encrypted at rest using AES-256 (provided by AWS/Supabase infrastructure).
- **Authentication**: Passwords are hashed using bcrypt. Sessions use signed JWT tokens with expiration.
- **Access control**: Row-Level Security (RLS) policies ensure each user can only access their own data.
- **API key storage**: On the desktop application, API keys are stored in your operating system's secure keychain (macOS Keychain, Windows Credential Manager, or Linux libsecret) and are never synced to the cloud.
- **Infrastructure**: Web services run on AWS with VPC isolation, security groups, and managed container orchestration.

No system is 100% secure. If you discover a security vulnerability, please contact us immediately at [SECURITY EMAIL].

---

## 8. Cookies and Tracking

### 8.1 What We Use

The Service uses only **essential cookies and local storage** required for the application to function:

- **Authentication tokens**: Stored in browser local storage to maintain your login session
- **Application state**: Stored in browser session storage for navigation between screens

### 8.2 What We Do NOT Use

- No third-party advertising cookies
- No cross-site tracking pixels
- No social media tracking scripts
- No fingerprinting or device identification for tracking purposes

### 8.3 Analytics

We collect aggregated, anonymized usage statistics (feature usage counts, error rates) for the purpose of improving the Service. These statistics cannot be linked back to individual users or their medical data.

---

## 9. Children's Privacy

The Service is not directed to individuals under the age of 18. We do not knowingly collect personal information from children. If we learn that we have collected data from a child under 18, we will delete it promptly. If you believe a child has provided us with personal information, contact us at [SUPPORT EMAIL].

---

## 10. International Data Transfers

The Service is operated in the United States. If you access the Service from outside the United States, your data will be transferred to and processed in the United States. By using the Service, you consent to this transfer.

For users in the European Economic Area (EEA) or United Kingdom: data transfers are conducted in compliance with applicable data protection laws, using Standard Contractual Clauses or other approved mechanisms where required.

---

## 11. California Privacy Rights (CCPA)

If you are a California resident, you have the right to:

- **Know** what personal information we collect, use, and disclose.
- **Delete** your personal information (see Section 6.2).
- **Opt-out of sale**: We do not sell your personal information.
- **Non-discrimination**: We will not discriminate against you for exercising your privacy rights.

To exercise these rights, use the self-service features in the application or contact us at [SUPPORT EMAIL].

---

## 12. Changes to This Privacy Policy

We may update this Privacy Policy from time to time. If we make material changes, we will notify you by email or through a notice in the Service at least 30 days before the changes take effect. The "Last Updated" date at the top of this page indicates when the policy was last revised.

---

## 13. Contact Us

For questions, concerns, or requests regarding this Privacy Policy or your personal data, contact us at:

**[YOUR LEGAL ENTITY NAME]**
Email: [SUPPORT EMAIL]
Privacy inquiries: [PRIVACY EMAIL]
