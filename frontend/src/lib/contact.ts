/**
 * Where the landing page's calls to action send people.
 *
 * Self-serve sign-up is deliberately not the front door yet: the first clients
 * come through a free audit run by hand, and — until the backend is hosted —
 * the sign-up form has nothing to talk to. One constant so the address is
 * changed in a single place rather than hunted through the markup.
 *
 * To use WhatsApp instead of email (better for this audience), set
 * WHATSAPP_NUMBER to the number in full international form, digits only, no
 * "+" and no spaces — e.g. "923001234567" for 0300 1234567.
 */
const WHATSAPP_NUMBER = "";

const EMAIL = "fatimakhalidddd0@gmail.com";

const ENQUIRY =
  "Hi, I'd like a free ad spend audit. I spend about Rs. ____ a month on Meta/Google ads.";

export const AUDIT_CONTACT_HREF = WHATSAPP_NUMBER
  ? `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(ENQUIRY)}`
  : `mailto:${EMAIL}?subject=${encodeURIComponent(
      "Free ad spend audit",
    )}&body=${encodeURIComponent(ENQUIRY)}`;

export const AUDIT_CTA_LABEL = "Get a free audit";
