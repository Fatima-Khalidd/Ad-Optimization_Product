/**
 * Where the landing page's calls to action send people.
 *
 * Self-serve sign-up is deliberately not the front door yet: the first clients
 * come through a free audit run by hand, and — until the backend is hosted —
 * the sign-up form has nothing to talk to.
 *
 * The buttons scroll to an on-page contact block rather than firing a
 * `mailto:` straight from the hero. A `mailto:` silently does nothing on a
 * machine with no mail client configured, which is most Windows machines —
 * the visitor clicks the main call to action and the page appears broken.
 * Showing the address as selectable text always works.
 *
 * To offer WhatsApp (better for this audience), set WHATSAPP_NUMBER to the
 * number in full international form, digits only, no "+" and no spaces —
 * e.g. "923001234567" for 0300 1234567. The block appears by itself.
 */
export const WHATSAPP_NUMBER = "";

export const CONTACT_EMAIL = "fatimakhalidddd0@gmail.com";

const ENQUIRY =
  "Hi, I'd like a free ad spend audit. I spend about Rs. ____ a month on Meta/Google ads.";

export const MAILTO_HREF = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(
  "Free ad spend audit",
)}&body=${encodeURIComponent(ENQUIRY)}`;

export const WHATSAPP_HREF = WHATSAPP_NUMBER
  ? `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(ENQUIRY)}`
  : null;

/** Every call to action points here; the section itself holds the real links. */
export const AUDIT_CONTACT_HREF = "#contact";
export const AUDIT_CTA_LABEL = "Get a free audit";
