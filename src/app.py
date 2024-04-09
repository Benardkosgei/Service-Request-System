import os
import sys
import json
import datetime
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_mail import Mail, Message

# Load .env
load_dotenv()

# Configure app settings
app = Flask(__name__, static_url_path='', static_folder='static')
app.secret_key = os.getenv("FLASK_APP_SECRET").encode()
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=1)

# Initialize Flask-Mail

# Configure Flask-Mail
app.config.update(dict(
    DEBUG = True,
    MAIL_SERVER = 'smtp.gmail.com',
    SECRET_KEY='ggdajhsdugshsdds232eytroroziqab',
    MAIL_PORT = 587,
    MAIL_USE_TLS = True,
    MAIL_USE_SSL = False,
    MAIL_USERNAME = 'your email ',
    MAIL_PASSWORD = 'app_password',
))
mail = Mail(app)

# Load service categories' description
with open(file=os.getenv('SC_CACHE_FILE'), mode='r') as sc_cache:
    try:
        service_categories = json.loads(sc_cache.read())
    except Exception as e:
        print('[ERROR]', e, file=sys.stderr)
        print("UNABLE TO LOAD SERVICE CATEGORIES' CACHE FILE", file=sys.stderr)
        sys.exit(1)

# Create Mongo Client & Connect to Database
client = MongoClient(os.getenv('MONGODB_URI'), tls=True, tlsCertificateKeyFile=os.getenv('MONGODB_PEM'))

db = client['service_request_system']
contact_collection = db['contact']
customers = db['customers']
vendors = db['vendors']
service_requests = db['service_requests']
bids = db['bids']

# ==================== Routings ==================== #

#> GENERAL ROUTES

@app.route('/', methods=['GET'])
def index():
    reviews = db.reviews.find()
    return render_template('index.html', service_categories=service_categories,reviews=reviews)

@app.route('/about', methods=['GET'])
def about_us():
    return render_template('about.html')

@app.route('/services', methods=['GET'])
def our_services():
    return render_template('services.html', service_categories=service_categories)

@app.route('/contact', methods=['GET', 'POST'])
def contact_us():
    match request.method:
        case 'GET':
            return render_template('contact.html')
        case 'POST':
            name = request.form['name']
            email = request.form['email']
            message = request.form['message']

            try:
                _ = contact_collection.insert_one(dict(name=name, email=email, message=message))
            except Exception as e:
                flash(f'{e}', 'error')
                return redirect('/contact')

            flash("Request submitted successfully! We'll get back soon.", 'success')
            return redirect('/contact')

@app.route('/roles', methods=['GET'])
def choose_role():
    if 'user_id' in session or 'email' in session:
        if session['user_role'] in {'customer', 'vendor'}:
            flash(f'{session["user_role"].capitalize()} session recovered! Skipping auth...', 'info')
            return redirect(f"/{session['user_role']}/dashboard")
        flash('Closing a previous session for security reasons...', 'info')
        return redirect('/logout')
    return render_template('request.html', service_categories=service_categories)

@app.route('/anonymous/new', methods=['POST'])
def anonymous_request():
    try:
        title = request.form['title']
        category = request.form['category']
        date = request.form['date']
        description = request.form['description']
        phone = request.form['phone']
        email = request.form['email']

        _ack = service_requests.insert_one(
                    dict(title=title,
                        category=category,
                        date=date,
                        description=description,
                        phone=phone,
                        email=email,
                        status='Open',
                        customer_id='anonymous'
                    )
        )

        flash(f'New service request #{_ack.inserted_id} raised successfully!', 'success')
        return redirect('/roles')
    except Exception as e:
        flash(f'{e}', 'error')
        return redirect('/roles')

@app.route('/forgot', methods=['GET', 'POST'])
def forgot_password():
    match request.method:
        case 'GET':
            return render_template('forgot.html')
        case 'POST':
            email = request.form['email']
            flash(f"Please check the inbox of {email}", 'info')
            return redirect('/forgot')

@app.route('/logout', methods=['GET'])
def logout_session():
    if 'user_id' not in session or 'email' not in session:
        flash("Something went wrong! Session lost...", 'error')
        return redirect('/contact')

    # Log out user session
    session.pop('user_id', None)
    session.pop('user_role', None)
    session.pop('email', None)
    return redirect(url_for('index'))

#> CUSTOMER ROUTES

@app.route('/customer/register', methods=['POST'])
def customer_register():
    try:
        name = request.form['fullname']
        email = request.form['email']
        phone = request.form['phone']
        password = generate_password_hash(request.form['password'], method=os.getenv('HASH_METHOD'))

        # Check if a customer already exist with similar creds
        if customers.find_one(dict(email=email)):
            flash(f'User already exists! Please login.', 'warning')
            return redirect('/customer/login')

        _ = customers.insert_one(dict(name=name, email=email, phone=phone, password=password))
    except Exception as e:
            flash(f'{e}', 'error')
            return redirect('/customer/login')

    flash(f'Hey {name}! Please login.', 'success')
    return render_template('customer/register_login.html')

@app.route('/customer/login', methods=['GET', 'POST'])
def customer_login():
    if 'user_id' in session or 'email' in session:
        if session['user_role'] != 'customer':
            flash('Closing a previous session for security reasons...', 'info')
            return redirect('/logout')
        flash('Recovered previous session! Login skipped...', 'info')
        return redirect('/customer/dashboard')

    match request.method:
        case 'GET':
            return render_template('customer/register_login.html')
        case 'POST':
            try:
                email = request.form['email']
                _password = request.form['password']

                customer = customers.find_one(dict(email=email))
                if customer:
                    if check_password_hash(customer['password'], _password):

                        # Login customer session
                        session['user_id'] = str(customer['_id'])
                        session['user_role'] = 'customer'
                        session['email'] = email

                        flash(f'Welcome {customer["name"]}!', 'success')
                        return redirect('/customer/dashboard')

                    flash(f'Please re-check your password and try again!', 'warning')
                    return redirect('/customer/login')

                flash('Please register! No record of the user exists.', 'error')
                return redirect('/customer/login')
            except Exception as e:
                flash(f'{e}', 'error')
                return redirect('/customer/login')

@app.route('/customer/dashboard', methods=['GET'])
def customer_dashboard():
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/customer/login')

    try:
        requests = service_requests.find(dict(customer_id=ObjectId(session['user_id'])))
        return render_template('customer/dashboard.html', requests=requests, dt=datetime.datetime)
    except Exception as e:
        flash(f'{e}', 'error')
        return redirect('/roles')

@app.route('/customer/history', methods=['GET'])
def customer_order_history():
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/customer/login')

    try:
        requests = service_requests.find(dict(customer_id=ObjectId(session['user_id']), status="Paid"))
        return render_template('customer/order_history.html', requests=requests, dt=datetime.datetime)
    except Exception as e:
        flash(f'{e}', 'error')
        return redirect('/roles')

@app.route('/customer/request/new', methods=['GET', 'POST'])
def place_new_request():
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/customer/login')

    match request.method:
        case 'GET':
            return render_template('customer/new_request.html', service_categories=service_categories)
        case 'POST':
            try:
                title = request.form['title']
                category = request.form['category']
                date = request.form['date']
                description = request.form['description']
                customer = customers.find_one({'_id': ObjectId(session['user_id'])})
                _ack = service_requests.insert_one(
                                dict(title=title,
                                    category=category,
                                    date=date,
                                    description=description,
                                    status='Open',
                                    customer_id=customer['_id'],
                                    phone=customer['phone'],
                                    email=customer['email'],
                                )
                    )

                flash(f'New service request #{_ack.inserted_id} placed!', 'success')
                return redirect('/customer/dashboard')
            except Exception as e:
                flash(f'{e}', 'error')
                return redirect('/customer/dashboard')

@app.route('/customer/request/edit/<request_id>', methods=['GET', 'POST'])
def edit_service_request(request_id):
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/customer/login')

    match request.method:
        case 'GET':
            sr = service_requests.find_one({'_id': ObjectId(request_id)})
            return render_template('customer/edit_request.html', request=sr, service_categories=service_categories)
        case 'POST':
            try:
                title = request.form['title']
                category = request.form['category']
                date = request.form['date']
                description = request.form['description']
                _ack = service_requests.update_one(
                        {'_id': ObjectId(request_id), 'customer_id': ObjectId(session['user_id'])},
                        {'$set': dict(title=title, category=category, date=date, description=description)}
                    )

                flash(f'Service request #{request_id} modified!', 'success')
                return redirect('/customer/dashboard')
            except Exception as e:
                flash(f'{e}', 'error')
                return redirect('/customer/dashboard')

@app.route('/customer/request/delete/<request_id>', methods=['GET'])
def delete_service_request(request_id):
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/customer/login')

    try:
        _ack = service_requests.delete_one({
            '_id': ObjectId(request_id),
            'customer_id': ObjectId(session['user_id'])
        })

        flash(f'Service request #{request_id} deleted!', 'success')
        return redirect('/customer/dashboard')
    except Exception as e:
        flash(f'{e}', 'error')
        return redirect('/customer/dashboard')

@app.route('/customer/request/bids/<request_id>', methods=['GET'])
def customer_request_bids(request_id):
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/customer/login')

    try:
        request_bids = bids.find(dict(request_id=ObjectId(request_id)))
        return render_template('customer/request_bids.html', request_id=request_id, bids=request_bids, str=str)
    except Exception as e:
        flash(f'{e}', 'error')
        return redirect('/customer/dashboard')

@app.route('/customer/request/<request_id>/vendor/<bid_id>', methods=['GET'])
def customer_request_bid_vendor(request_id, bid_id):
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/customer/login')

    try:
        _bid = bids.find_one({'_id': ObjectId(bid_id)})
        vendor = vendors.find_one({'_id': ObjectId(_bid['vendor_id'])})
        return render_template('customer/view_vendor.html', vendor=vendor)
    except Exception as e:
        flash(f'{e}', 'error')
        return redirect('/customer/dashboard')

@app.route('/customer/request/<request_id>/bid/<bid_id>', methods=['GET'])
def customer_request_accept_bid(request_id, bid_id):
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/customer/login')

    try:
        bid = bids.find_one({'_id': ObjectId(bid_id)})
        vendor = vendors.find_one({'_id': ObjectId(bid['vendor_id'])})
        _sr_ack = service_requests.update_one({'_id': ObjectId(request_id)}, {
                                                '$set': dict(status='Closed',
                                                        vendor_id=vendor['_id'],
                                                        vendor_phone=vendor['phone'],
                                                        vendor_email=vendor['email'],
                                                        amount=bid['amount'])
                                            })
        return redirect('/customer/dashboard')
    except Exception as e:
        flash(f'{e}', 'error')
        return redirect('/customer/dashboard')

@app.route('/customer/request/<request_id>/rate/<vendor_id>', methods=['GET', 'POST'])
def customer_rate_vendor(request_id, vendor_id):
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/customer/login')

    match request.method:
        case 'GET':
            vendor = vendors.find_one({'_id': ObjectId(vendor_id)})
            return render_template('customer/rate_vendor.html', request_id=request_id, vendor=vendor)
        case 'POST':
            try:
                rating = request.form['rating']; rating = int(rating) if rating else 0
                comment = request.form['comment']
                _sr_ack = service_requests.update_one({'_id': ObjectId(request_id), 'vendor_id': ObjectId(vendor_id)},
                                                      {'$set': dict(status='Rated', rating=rating, comment=comment)})
                return redirect('/customer/dashboard')
            except Exception as e:
                flash(f'{e}', 'error')
                return redirect('/customer/dashboard')

@app.route('/customer/request/<request_id>/pay/<vendor_id>', methods=['GET', 'POST'])
def customer_pay_vendor(request_id, vendor_id):
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/customer/login')

    match request.method:
        case 'GET':
            vendor = vendors.find_one({'_id': ObjectId(vendor_id)})
            sr = service_requests.find_one({'_id': ObjectId(request_id), 'vendor_id': vendor['_id']})
            return render_template('customer/pay_vendor.html', request=sr, vendor=vendor)
        case 'POST':
            try:
                # Card Details
                payment_gateway = request.form['payment_gateway']
                amount = int(request.form['amount'])
                email = request.form['email']
                _sr_ack = service_requests.update_one({'_id': ObjectId(request_id), 'vendor_id': ObjectId(vendor_id)},
                                                      {'$set': dict(status='Paid', payment_gateway=payment_gateway)})
                # Send payment confirmation email
                customer = customers.find_one({'_id': ObjectId(session['user_id'])})
                send_email(
                    subject='Payment Confirmation',
                    recipients=[customer['email']],
                    body=f'Your payment for service request has been successfully processed of $ {amount}. Thank you for your payment!',
                )
                flash(f'Thanks for finishing the payment towards #Vendor<{vendor_id}>', 'success')
                return redirect('/customer/dashboard')
            except Exception as e:
                flash(f'{e}', 'error')
                return redirect('/customer/dashboard')
            
#PROFILE
@app.route('/customer/profile', methods=['GET'])
def customer_profile():
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/customer/login')
    try:
        customer = customers.find_one({'_id': ObjectId(session['user_id'])})
        return render_template('customer/profile.html', customer=customer)
    except Exception as e:
        flash(f'{e}', 'error')
        return redirect('/customer/dashboard')
    
#edit profile
# Update the edit_customer_profile route
@app.route('/customer/profile/edit', methods=['GET', 'POST'])
def edit_customer_profile():
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/customer/login')

    if request.method == 'GET':
        try:
            customer = customers.find_one({'_id': ObjectId(session['user_id'])})
            return render_template('customer/edit_profile.html', customer=customer)
        except Exception as e:
            flash(f'{e}', 'error')
            return redirect('/customer/dashboard')
    elif request.method == 'POST':
        try:
            name = request.form['fullname']
            email = request.form['email']
            phone = request.form['phone']
            # Get the current customer data
            current_customer = customers.find_one({'_id': ObjectId(session['user_id'])})
            # Update the customer's profile
            customers.update_one({'_id': ObjectId(session['user_id'])},
                                 {'$set': {'name': name, 'email': email, 'phone': phone}})
            # Send profile update confirmation email
            email_body = render_template('customer/profile_update_confirmation.html', 
                                         old_customer=current_customer, 
                                         new_customer={'name': name, 'email': email, 'phone': phone})
            send_email(subject='Profile Update Confirmation', recipients=[email], body=email_body)

            flash('Profile updated successfully! Profile update confirmation email sent.', 'success')
            return redirect('/customer/profile')
        except Exception as e:
            flash(f'{e}', 'error')
            return redirect('/customer/profile')

# Function to send email
def send_email(subject, recipients, body):
    try:
        message = Message(
            subject=subject,
            recipients=recipients,
            sender='flask254@gmail.com'
        )
        message.html = body
        mail.send(message)
    except Exception as e:
        print(f"Error sending email: {e}")


# CUSTOMER REVIEWS
@app.route('/customer/reviews', methods=['GET'])
def customer_review():
       # Fetch reviews from the database
    reviews = db.reviews.find()
    return render_template('customer/customer_review.html',reviews=reviews)
 
 
@app.route('/customer/create_review', methods=['GET'])
def create_review():
    try:
        # Fetch categories from the service categories loaded from the cache
        categories = service_categories
        return render_template('customer/create_review.html', categories=categories)
    except Exception as e:
        flash(f'{e}', 'error')
        return redirect('/customer/dashboard')
    
#create review
@app.route('/customer/review/create', methods=['POST'])
def submit_review():
    # Get data from the form
    title = request.form['title']
    description = request.form['description']
    category= request.form['category']
    # Insert the review into the database
    db.reviews.insert_one({'title': title, 'description': description,'category':category})
    # Redirect to reviews
    return redirect('/customer/reviews')
#remove review
# Add this route to handle review deletion
@app.route('/customer/review/delete/<review_id>', methods=['GET'])
def delete_review(review_id):
    try:
        # Assuming you have a collection called 'reviews' in your MongoDB
        # Delete the review from the database
        db.reviews.delete_one({'_id': ObjectId(review_id)})
        flash('Review deleted successfully!', 'success')
    except Exception as e:
        flash(f'An error occurred while deleting the review: {e}', 'error')
    return redirect('/customer/reviews')

#> VENDOR ROUTES

@app.route('/vendor/register', methods=['POST'])
def vendor_register():
    try:
        name = request.form['fullname']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        (latitude, longitude) = request.form['latitude'], request.form['longitude']
        password = generate_password_hash(request.form['password'], method=os.getenv('HASH_METHOD'))

        # Check if a vendor already exist with similar creds
        if vendors.find_one(dict(email=email)):
            flash(f'User already exists! Please login.', 'warning')
            return redirect('/vendor/login')

        _ = vendors.insert_one(dict(name=name,
                                    email=email,
                                    phone=phone,
                                    address=address,
                                    latitude=latitude, longitude=longitude,
                                    password=password))
    except Exception as e:
            flash(f'{e}', 'error')
            return redirect('/vendor/login')

    flash(f'Hey {name}! Please login.', 'success')
    return render_template('vendor/register_login.html')

@app.route('/vendor/login', methods=['GET', 'POST'])
def vendor_login():
    if 'user_id' in session or 'email' in session:
        if session['user_role'] != 'vendor':
            flash('Closing a previous session for security reasons...', 'info')
            return redirect('/logout')
        flash('Recovered previous session! Login skipped...', 'info')
        return redirect('/vendor/dashboard')

    match request.method:
        case 'GET':
            return render_template('vendor/register_login.html')
        case 'POST':
            try:
                email = request.form['email']
                _password = request.form['password']

                vendor = vendors.find_one(dict(email=email))
                if vendor:
                    if check_password_hash(vendor['password'], _password):

                        # Login vendor session
                        session['user_id'] = str(vendor['_id'])
                        session['user_role'] = 'vendor'
                        session['email'] = email

                        flash(f'Welcome {vendor["name"]}!', 'success')
                        return redirect('/vendor/dashboard')

                    flash(f'Please re-check your password and try again!', 'warning')
                    return redirect('/vendor/login')

                flash('Please register! No record of the user exists.', 'error')
                return redirect('/vendor/login')
            except Exception as e:
                flash(f'{e}', 'error')
                return redirect('/vendor/login')

@app.route('/vendor/dashboard', methods=['GET'])
def vendor_dashboard():
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/vendor/login')

    try:
        requests = service_requests.find()
        return render_template('vendor/dashboard.html', requests=requests, dt=datetime.datetime)
    except Exception as e:
        flash(f'{e}', 'error')
        return redirect('/roles')

@app.route('/vendor/history', methods=['GET'])
def vendor_order_history():
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/customer/login')

    try:
        requests = service_requests.find(dict(vendor_id=ObjectId(session['user_id']), status={'$ne': 'Open'}))
        return render_template('vendor/order_history.html', requests=requests, dt=datetime.datetime)
    except Exception as e:
        flash(f'{e}', 'error')
        return redirect('/roles')



@app.route('/vendor/bid/<request_id>', methods=['GET', 'POST'])
def vendor_bid(request_id):
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/vendor/login')

    match request.method:
        case 'GET':
            sr = service_requests.find_one({'_id': ObjectId(request_id)})
            return render_template('vendor/bid_request.html', request=sr, email=session['email'], dt=datetime.datetime, service_categories=service_categories)
        case 'POST':
            try:
                amount = request.form['amount']
                message = request.form.get('message', '')
                email = request.form['email']

                sr = service_requests.find_one({'_id': ObjectId(request_id)})
                _ack = bids.insert_one(
                        dict(request_id=ObjectId(request_id),
                            amount=amount,
                            message=message,
                            email=email,
                            vendor_id=ObjectId(session['user_id']),
                            customer_id=sr['customer_id']
                        )
                )

                flash(f'Bid #{_ack.inserted_id} submitted successfully!', 'success')
                return redirect('/vendor/dashboard')
            except Exception as e:
                flash(f'{e}', 'error')
                return redirect('/vendor/dashboard')

@app.route('/vendor/bids', methods=['GET'])
def vendor_request_bids():
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/vendor/login')

    try:
        vendor_bids = list(bids.find(dict(vendor_id=ObjectId(session['user_id']))))
        sr_ids = set(ObjectId(bid['request_id']) for bid in vendor_bids)
        sreqs = service_requests.find({'_id': {'$in': list(sr_ids)}})
        active_bids = set(sreq['_id'] for sreq in sreqs if sreq['status'].lower() == 'open')
        return render_template('vendor/active_bids.html',
                    bids=list(bid for bid in vendor_bids if bid['request_id'] in active_bids), str=str)
    except Exception as e:
        flash(f'{e}', 'error')
        return redirect('/vendor/dashboard')

@app.route('/vendor/bid/<bid_id>/request/<request_id>', methods=['GET'])
def vendor_view_bid_request(bid_id, request_id):
    if 'user_id' not in session or 'email' not in session:
        flash('Denied access! Please login to continue.', 'error')
        return redirect('/vendor/login')

    try:
        sr = service_requests.find_one({'_id': ObjectId(request_id)})
        bid = bids.find_one({'_id': ObjectId(bid_id)})
        return render_template('vendor/view_request.html', request=sr, bid=bid, dt=datetime.datetime, service_categories=service_categories)
    except Exception as e:
        flash(f'{e}', 'error')
        return redirect('/vendor/dashboard')


if __name__ == "__main__":
    app.run(debug=True)
