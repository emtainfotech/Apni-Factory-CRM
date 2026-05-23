# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Admin(models.Model):
    id = models.BigAutoField(primary_key=True)
    attribute = models.CharField(max_length=100)
    value = models.TextField()
    usedin = models.CharField(max_length=100)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Admin'


class Advertisements(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    content = models.CharField(max_length=255)
    file = models.CharField(max_length=255)
    user_id = models.IntegerField()
    status = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    adminmsg = models.CharField(max_length=255)
    screen = models.CharField(max_length=20)
    enddate = models.DateField(blank=True, null=True)
    startdate = models.DateField(blank=True, null=True)
    sequence = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'advertisements'


class BankDetails(models.Model):
    id = models.BigAutoField(primary_key=True)
    accountholder = models.CharField(max_length=255, blank=True, null=True)
    accountno = models.CharField(max_length=255, blank=True, null=True)
    bankname = models.CharField(max_length=255, blank=True, null=True)
    branch = models.CharField(max_length=255, blank=True, null=True)
    ifsc = models.CharField(max_length=255, blank=True, null=True)
    isprimary = models.CharField(max_length=1)
    user_id = models.IntegerField()
    status = models.CharField(max_length=8)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    company_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'bank_details'


class BoxPackings(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    pcs = models.IntegerField()
    status = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    maincategory_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'box_packings'


class Brands(models.Model):
    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField()
    name = models.CharField(max_length=100)
    status = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    user_id = models.IntegerField()
    mid = models.IntegerField()
    category_id = models.IntegerField()
    image = models.TextField()
    trademarkno = models.CharField(max_length=100)
    file = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=20)
    adminresponse = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'brands'


class Cart(models.Model):
    product_id = models.IntegerField()
    customer_id = models.IntegerField()
    createat = models.DateTimeField()
    updateat = models.DateTimeField()
    productname = models.TextField()
    company_id = models.IntegerField()
    brand_id = models.IntegerField()
    category_id = models.IntegerField()
    couponbyadmin = models.TextField(blank=True, null=True)
    addressid = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'cart'


class Cartattribute(models.Model):
    customer_id = models.IntegerField()
    cart_id = models.IntegerField()
    product_attributes_id = models.IntegerField()
    qty = models.IntegerField()
    boxpcs = models.IntegerField()
    prprice = models.IntegerField()
    coupon = models.FloatField()
    amntaftrcoupn = models.FloatField()
    unitprice = models.FloatField()
    totalprice = models.FloatField()
    couponname = models.TextField(blank=True, null=True)
    tax = models.IntegerField()
    taxamount = models.FloatField()

    class Meta:
        managed = False
        db_table = 'cartattribute'


class Categories(models.Model):
    id = models.BigAutoField(primary_key=True)
    maincategory_id = models.IntegerField()
    name = models.CharField(unique=True, max_length=100)
    title = models.CharField(max_length=255)
    image = models.CharField(max_length=255)
    status = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    addby = models.IntegerField(db_comment='requestby')
    adminmsg = models.CharField(max_length=255, blank=True, null=True)
    adminstatus = models.CharField(max_length=10)
    sequence = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'categories'


class Comments(models.Model):
    user_id = models.PositiveIntegerField()
    product_id = models.PositiveIntegerField()
    text = models.TextField(db_collation='utf8mb4_unicode_ci')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'comments'


class Companies(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    status = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    user_id = models.IntegerField()
    email = models.CharField(max_length=50)
    mobile = models.CharField(max_length=20)
    maincategory_id = models.IntegerField()
    gst = models.CharField(max_length=20)
    crn = models.CharField(max_length=20)
    minordervalue = models.IntegerField()
    photo = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=20)
    state = models.CharField(max_length=30)
    pincode = models.IntegerField()
    comission = models.IntegerField()
    restricted_city = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'companies'


class Coupons(models.Model):
    code = models.CharField(max_length=191, db_collation='utf8mb4_unicode_ci')
    type = models.CharField(max_length=10)
    price = models.FloatField()
    description = models.TextField(db_collation='utf8mb4_unicode_ci')
    startdate = models.DateField()
    expiry = models.DateField()
    status = models.IntegerField()
    name = models.CharField(max_length=255)
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    image = models.TextField(blank=True, null=True)
    couponon = models.CharField(max_length=10)
    user_id = models.IntegerField()
    couponapplyon = models.TextField()

    class Meta:
        managed = False
        db_table = 'coupons'


class Credits(models.Model):
    user_id = models.IntegerField()
    order_id = models.IntegerField()
    orderno = models.CharField(max_length=200)
    value = models.CharField(max_length=200)
    commission = models.FloatField()
    refundtobuyer = models.FloatField()
    debit = models.FloatField()
    credit = models.FloatField()
    balance = models.FloatField()
    addby = models.CharField(max_length=100)
    msg = models.TextField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'credits'


class CustomerAddresses(models.Model):
    id = models.BigAutoField(primary_key=True)
    customer_id = models.IntegerField()
    landmark1 = models.CharField(max_length=255)
    landmark2 = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    pincode = models.CharField(max_length=255)
    country = models.CharField(max_length=255)
    phoneno = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    identityname = models.CharField(max_length=255)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    type = models.CharField(max_length=10)

    class Meta:
        managed = False
        db_table = 'customer_addresses'


class Customers(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    email = models.CharField(unique=True, max_length=255)
    mobile = models.CharField(unique=True, max_length=255, blank=True, null=True)
    whatsappno = models.CharField(max_length=12)
    gstorpan = models.CharField(max_length=30, blank=True, null=True)
    lastlogin = models.DateTimeField(blank=True, null=True)
    password = models.CharField(max_length=255, blank=True, null=True)
    type = models.CharField(max_length=6)
    status = models.CharField(max_length=8)
    remember_token = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    firebaseid = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    followers = models.IntegerField()
    following = models.IntegerField()
    image = models.CharField(max_length=255, blank=True, null=True)
    otp = models.IntegerField()
    regby = models.CharField(max_length=10)

    class Meta:
        managed = False
        db_table = 'customers'


class FailedJobs(models.Model):
    id = models.BigAutoField(primary_key=True)
    uuid = models.CharField(unique=True, max_length=255)
    connection = models.TextField()
    queue = models.TextField()
    payload = models.TextField()
    exception = models.TextField()
    failed_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'failed_jobs'


class Faqs(models.Model):
    id = models.BigAutoField(primary_key=True)
    question = models.CharField(max_length=255)
    answer = models.TextField()
    status = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    user_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'faqs'


class Feedback(models.Model):
    id = models.BigAutoField(primary_key=True)
    customer_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    feedback = models.CharField(max_length=255)
    status = models.CharField(max_length=8)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'feedback'


class Images(models.Model):
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'images'


class IndiaPincode(models.Model):
    city = models.CharField(max_length=25, blank=True, null=True)
    area = models.CharField(max_length=39, blank=True, null=True)
    pincode = models.CharField(max_length=7, blank=True, null=True)
    district = models.CharField(max_length=30, blank=True, null=True)
    state = models.CharField(max_length=20, blank=True, null=True)
    col_6 = models.CharField(db_column='COL 6', max_length=9, blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.

    class Meta:
        managed = False
        db_table = 'india_pincode'


class IndiaPincodeOld(models.Model):
    city = models.CharField(max_length=25, blank=True, null=True)
    area = models.CharField(max_length=39, blank=True, null=True)
    pincode = models.CharField(max_length=7, blank=True, null=True)
    district = models.CharField(max_length=30, blank=True, null=True)
    state = models.CharField(max_length=20, blank=True, null=True)
    col_6 = models.CharField(db_column='COL 6', max_length=9, blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.

    class Meta:
        managed = False
        db_table = 'india_pincode_old'


class Logsofpages(models.Model):
    actionon = models.CharField(max_length=200)
    request = models.TextField()
    response = models.TextField()
    updateon = models.DateField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'logsofpages'


class MainCategories(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=100)
    title = models.CharField(max_length=255)
    image = models.CharField(max_length=255)
    status = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    sequence = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'main_categories'


class Migrations(models.Model):
    migration = models.CharField(max_length=255)
    batch = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'migrations'


class Notifications(models.Model):
    customer_id = models.IntegerField()
    msgread = models.IntegerField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    title = models.TextField()
    body = models.TextField()
    customertype = models.CharField(max_length=8)

    class Meta:
        managed = False
        db_table = 'notifications'


class OrderStatus(models.Model):
    order_id = models.IntegerField()
    order_no = models.CharField(max_length=200)
    status = models.CharField(max_length=100)
    msg = models.TextField()
    user_id = models.IntegerField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'order_status'


class OrderTracks(models.Model):
    order_id = models.IntegerField()
    transname = models.TextField(db_collation='utf8mb4_unicode_ci', blank=True, null=True)
    text = models.TextField(db_collation='utf8mb4_unicode_ci', blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    transcontact = models.CharField(max_length=20)
    lrno = models.CharField(max_length=20)
    status = models.IntegerField()
    orderno = models.CharField(max_length=20)
    creditamnt = models.FloatField()
    invoiceno = models.CharField(max_length=200, blank=True, null=True)
    billty = models.TextField(blank=True, null=True)
    invoice = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'order_tracks'


class Orderdetail(models.Model):
    order_id = models.IntegerField()
    orderno = models.CharField(max_length=100)
    customer_id = models.IntegerField()
    product_id = models.IntegerField()
    productname = models.CharField(max_length=200)
    hsn = models.CharField(max_length=20)
    brdcmpcat = models.TextField(db_comment='company/category/brand')
    attribute = models.TextField()
    coupondetail = models.TextField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'orderdetail'


class OrderdetailOld(models.Model):
    product_id = models.IntegerField()
    productname = models.CharField(max_length=200)
    brand = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    price = models.FloatField()
    attribute = models.TextField()
    customer_id = models.IntegerField()
    order_id = models.IntegerField()
    company = models.CharField(max_length=100)
    orderno = models.CharField(max_length=100)
    hsn = models.CharField(max_length=20)
    admincoupon = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'orderdetail_old'


class Orders(models.Model):
    orderno = models.CharField(max_length=50)
    customer_id = models.IntegerField()
    user_id = models.IntegerField()
    address = models.TextField()
    sellercouponamount = models.FloatField(db_comment='attributededucted')
    admincouponamount = models.FloatField()
    admincoupondetail = models.TextField()
    netamount = models.FloatField(db_comment='afteralldiscount')
    taxdetail = models.TextField()
    taxamount = models.FloatField()
    grandtotal = models.FloatField(db_comment='net+tax')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'orders'


class OrdersOld(models.Model):
    orderno = models.CharField(max_length=50)
    customer_id = models.IntegerField()
    user_id = models.IntegerField()
    address = models.TextField()
    coupon_code = models.TextField()
    couponamount = models.FloatField()
    created_at = models.DateTimeField()
    amount = models.FloatField()
    tax = models.FloatField()
    grandtotal = models.FloatField()
    txn_id = models.CharField(max_length=100)
    txnstatus = models.CharField(max_length=10)
    txnmethod = models.CharField(max_length=20)
    txndetail = models.TextField()
    txnresponse = models.TextField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'orders_old'


class Pages(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    slug = models.CharField(unique=True, max_length=255)
    description = models.TextField()
    status = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    user_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'pages'


class PasswordResets(models.Model):
    email = models.CharField(max_length=255)
    token = models.CharField(max_length=255)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'password_resets'


class PersonalAccessTokens(models.Model):
    id = models.BigAutoField(primary_key=True)
    tokenable_type = models.CharField(max_length=255)
    tokenable_id = models.PositiveBigIntegerField()
    name = models.CharField(max_length=255)
    token = models.CharField(unique=True, max_length=64)
    abilities = models.TextField(blank=True, null=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'personal_access_tokens'


class ProductAttributes(models.Model):
    id = models.BigAutoField(primary_key=True)
    product_id = models.CharField(max_length=255)
    color = models.CharField(max_length=255, db_comment='shadecardid')
    quantity = models.CharField(max_length=255)
    oldprice = models.FloatField()
    price = models.FloatField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'product_attributes'


class ProductImages(models.Model):
    id = models.BigAutoField(primary_key=True)
    product_id = models.CharField(max_length=255)
    image = models.TextField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'product_images'


class ProductReviews(models.Model):
    id = models.BigAutoField(primary_key=True)
    product_id = models.IntegerField()
    customer_id = models.IntegerField()
    rating = models.IntegerField()
    review = models.CharField(max_length=255)
    status = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'product_reviews'


class Products(models.Model):
    id = models.BigAutoField(primary_key=True)
    product_id = models.IntegerField()
    maincategory_id = models.IntegerField()
    category_id = models.IntegerField()
    subcategory_id = models.IntegerField()
    name = models.CharField(max_length=255)
    slug = models.CharField(unique=True, max_length=255)
    title = models.CharField(max_length=255)
    image = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField()
    multipleimages = models.TextField(blank=True, null=True)
    status = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    brand_id = models.IntegerField()
    user_id = models.IntegerField()
    hsncode = models.CharField(max_length=20)
    tax = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'products'


class Profiles(models.Model):
    attribute = models.CharField(max_length=100)
    value = models.CharField(max_length=100)
    viewon = models.CharField(max_length=50)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'profiles'


class RestrictedCity(models.Model):
    user_id = models.IntegerField()
    company_id = models.IntegerField()
    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    pincode = models.TextField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'restricted_city'


class ShadeCards(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    maincategory_id = models.IntegerField()
    category_id = models.IntegerField()
    hexcode = models.CharField(max_length=100, blank=True, null=True)
    image = models.CharField(max_length=200, blank=True, null=True)
    status = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    user_id = models.IntegerField()
    adminmsg = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'shade_cards'


class ShadeCardsOld(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    maincategory_id = models.IntegerField()
    category_id = models.IntegerField()
    hexcode = models.CharField(max_length=100)
    image = models.CharField(max_length=200, blank=True, null=True)
    status = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    user_id = models.IntegerField()
    adminmsg = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'shade_cards_old'


class Sizes(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=8)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'sizes'


class Sliders(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=100)
    image = models.CharField(max_length=255)
    status = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    screen = models.CharField(max_length=100)
    startdate = models.DateField()
    enddate = models.DateField()
    company_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'sliders'


class SubCategories(models.Model):
    id = models.BigAutoField(primary_key=True)
    maincategory_id = models.IntegerField()
    category_id = models.IntegerField()
    name = models.CharField(unique=True, max_length=100)
    title = models.CharField(max_length=255)
    image = models.CharField(max_length=255)
    status = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'sub_categories'


class TblOtp(models.Model):
    otpon = models.CharField(max_length=50)
    otp = models.IntegerField()
    createat = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'tbl_otp'


class Tickets(models.Model):
    id = models.BigAutoField(primary_key=True)
    topic = models.CharField(max_length=255)
    msg = models.CharField(max_length=255)
    adminmsg = models.CharField(max_length=255)
    user_id = models.IntegerField()
    status = models.CharField(max_length=9)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tickets'


class Transections(models.Model):
    order_id = models.IntegerField()
    order_no = models.CharField(max_length=200)
    customer_id = models.IntegerField()
    user_id = models.IntegerField()
    status = models.CharField(max_length=50)
    txnid = models.CharField(max_length=100)
    txndetail = models.TextField()
    txnresponse = models.TextField()
    txnmethod = models.CharField(max_length=200)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'transections'


class Users(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    email = models.CharField(unique=True, max_length=255)
    email_verified_at = models.DateTimeField(blank=True, null=True)
    password = models.CharField(max_length=255)
    remember_token = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = 'users'


class Wallet(models.Model):
    user_id = models.IntegerField()
    order_id = models.IntegerField()
    orderno = models.CharField(max_length=200)
    value = models.CharField(max_length=200)
    commission = models.FloatField()
    refundtobuyer = models.FloatField()
    debit = models.FloatField()
    credit = models.FloatField()
    balance = models.FloatField()
    addby = models.CharField(max_length=100)
    msg = models.TextField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    creditcreated = models.CharField(max_length=1)

    class Meta:
        managed = False
        db_table = 'wallet'


class Whatsappmsgs(models.Model):
    id = models.BigAutoField(primary_key=True)
    template = models.CharField(max_length=255)
    templateid = models.CharField(max_length=255)
    actionon = models.CharField(max_length=255)
    variables = models.CharField(max_length=255)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'whatsappmsgs'


class Wishlist(models.Model):
    userid = models.PositiveIntegerField()
    productid = models.PositiveIntegerField()
    productname = models.TextField()
    productimage = models.TextField()

    class Meta:
        managed = False
        db_table = 'wishlist'
