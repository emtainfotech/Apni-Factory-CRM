BOT_RESPONSES = {
    # --- NEW USER MENU ---
    "onboard_menu": (
        "👋 Welcome to Apni Factory! How can we help you today?\n"
        "1️⃣ Sell My Products\n"
        "2️⃣ Buy Products\n"
        "3️⃣ Contact Our Team\n"
        "4️⃣ About Apni Factory\n\n"
        "👉 *Reply with 1, 2, 3, or 4*"
    ),
    
    # --- SELL MY PRODUCTS ---
    "seller_business_type": (
        "Great! Please select your Business Type:\n"
        "1️⃣ Manufacturer\n"
        "2️⃣ Brand Owner\n"
        "3️⃣ Distributor\n"
        "4️⃣ Wholesaler\n"
        "5️⃣ Retailer\n"
        "6️⃣ Others\n\n"
        "👉 *Reply with the number*"
    ),
    "gst_request": (
        "Are you a GST Registered business? 📜\n\n"
        "Please reply with your **GST Number** to proceed, or type **NO** if you don't have one."
    ),
    "no_gst_notice": (
        "⚠️ GST is mandatory to sell as a Manufacturer on Apni Factory.\n\n"
        "If you'd like to register as a Buyer instead, or need help from our team, please let us know by typing *Help* or *Buyer*."
    ),
    "brand_owner_not_eligible": (
        "Brand Owners without their own manufacturing are not currently eligible as direct sellers.\n\n"
        "Our team will review your application. An executive will contact you shortly."
    ),
    "retailer_buyer_redirect": (
        "As a Distributor, Wholesaler, or Retailer, you can purchase directly from Manufacturers on our platform!\n\n"
        "We are setting up your Buyer profile. Please provide your Email Address to continue."
    ),
    "others_review": (
        "Thank you! We have collected your business details.\n"
        "Our team will review your request and get back to you shortly."
    ),
    "seller_collect_email": "Almost done! Please reply with your **Email Address**.",
    "seller_collect_category": "What **Category** of products do you manufacture? (e.g., Clothing, Electronics, Hardware)",
    "seller_collect_state": "Which **State** is your manufacturing unit located in?",
    "seller_success": (
        "🎉 Welcome aboard!\n\n"
        "Your Seller Account has been created and your Relationship Manager has been assigned.\n\n"
        "Download our App to start listing your products:\n"
        "📱 https://play.google.com/store/apps/details?id=com.app.apnifactory"
    ),

    # --- BUY PRODUCTS ---
    "buyer_collect_name": "Awesome! What is your **Full Name**?",
    "buyer_collect_email": "Please reply with your **Email Address**.",
    "buyer_success": (
        "🎉 Registration Successful!\n\n"
        "You can now browse products and place orders at direct factory prices. "
        "(GST is only required during checkout if you need a GST invoice).\n\n"
        "Download our App to start buying:\n"
        "📱 https://play.google.com/store/apps/details?id=com.app.apnifactory"
    ),

    # --- EXISTING SELLER ---
    "existing_seller_menu": (
        "Welcome back, {name}! 👋\n\n"
        "1️⃣ Orders\n"
        "2️⃣ Payments & Settlement\n"
        "3️⃣ Product Listing\n"
        "4️⃣ Marketing\n"
        "5️⃣ Technical Support\n"
        "6️⃣ Relationship Manager\n"
        "7️⃣ Request Callback\n"
        "8️⃣ Main Menu\n\n"
        "👉 *Reply with a number*"
    ),

    # --- EXISTING BUYER ---
    "existing_buyer_menu": (
        "Welcome back, {name}! 👋\n\n"
        "1️⃣ Browse Products\n"
        "2️⃣ My Orders\n"
        "3️⃣ Track Order\n"
        "4️⃣ Returns\n"
        "5️⃣ Login Help\n"
        "6️⃣ Contact Support\n\n"
        "👉 *Reply with a number*"
    ),

    # --- SUPPORT WORKFLOWS ---
    "ask_order_id": "Please reply with your **Order ID** and describe the issue (or send photos if damaged).",
    "ask_invoice_id": "Please reply with your **Invoice No** or **Settlement ID**.",
    "ask_login_screenshot": "Please reply with a screenshot of the login issue and mention your device (Android/iOS).",
    "ask_marketing_req": "Please describe your marketing requirement or the package you are interested in.",
    
    "support_ticket_created": (
        "Thank you! ✅\n\n"
        "We have collected the necessary details. A complete ticket has been created and assigned to the right department. "
        "An executive will join this chat shortly to assist you."
    ),

    # --- GENERAL ---
    "contact_team": (
        "Thank you for reaching out! ✅\n\n"
        "Our customer care executive has been notified and will contact you shortly to assist with your requirement. 📞"
    ),
    "about_apni_factory": (
        "Apni Factory is India's leading B2B platform connecting Manufacturers directly with Retailers and Wholesalers.\n\n"
        "We eliminate middlemen so sellers get better margins and buyers get factory prices!\n"
        "Type *Menu* to go back."
    ),
    "invalid_input": "I didn't understand that. 😕 Please reply with a valid option from the menu.",
    "gst_verified": "✅ *GST Verification Successful!*\n\n**Company:** {company_name}",
    "gst_failed": "❌ Invalid GST Number. Please check and try again, or type *NO* if you don't have one.",
}