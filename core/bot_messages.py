BOT_RESPONSES = {
    # --- EXISTING MESSAGES ---
    "onboard_menu": (
        "Welcome to ApniFactory! 👋\n\n"
        "Please choose an option:\n"
        "1️⃣ Sell Products\n"
        "2️⃣ Buy Products\n"
        "3️⃣ General Enquiry\n\n"
        "👉 *Reply with 1, 2, or 3*"
    ),
    "seller_segment": "Great! What describes you best?\n1️⃣ Manufacturer\n2️⃣ Distributor / Wholesaler\n3️⃣ Brand Owner / Importer\n\n👉 *Reply with the number*",
    "gst_confirm": "GST is required for sellers. 📜\n\nDo you have a valid GST number?\n👉 *Reply YES or NO*",
    "gst_input": "Please enter your **GST Number** below. 👇",
    "no_gst_notice": "⚠️ GST is mandatory. Please message us again once you have a GST number.",
    "gst_verified": "✅ *Verification Successful!*\n\n**Company:** {company_name}\n**Status:** Verified\n\nYour seller account is active.",
    "gst_failed": "❌ Invalid GST Number. Please try again or type *'Human'* for help.",
    "buyer_segment": "What kind of buyer are you?\n1️⃣ Business / Shop Owner\n2️⃣ Personal Use\n\n👉 *Reply with 1 or 2*",
    "buyer_success": "🎉 Your buyer profile is set! Download our app to start ordering.",
    "general_inquiry": "ApniFactory is India's leading B2B platform. Type your query below.",
    "invalid_input": "I didn't understand that. 😕 Please reply with the correct option.",

    # --- NEW: VERIFIED USER FLOW ---
    "verified_welcome": (
        "Welcome back, {name}! 👋\n\n"
        "How can we help you today?"
    ),
    "support_contact": (
        "Thank you for your message! ✅\n\n"
        "Our customer care executive has been notified and will contact you shortly to assist with your requirement. 📞"
    ),
}