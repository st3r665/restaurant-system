# app.py
import os
from datetime import datetime, timedelta, time, date
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)

# --- 配置 ---
app.secret_key = os.urandom(24)

# MySQL配置 (请根据你的MySQL设置修改)
app.config['MYSQL_HOST'] = '192.168.56.131'
app.config['MYSQL_USER'] = 'star'
app.config['MYSQL_PASSWORD'] = 'Xsy_041207'
app.config['MYSQL_DB'] = 'restaurant_db'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# --- 辅助函数 ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录才能访问此页面。', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash('您没有权限访问此页面。', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def get_available_time_slots():
    slots = []
    for hour in range(10, 22):
        slots.append(time(hour, 0).strftime('%H:%M'))
    return slots

# --- 上下文处理器 ---
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow}

# --- 核心路由 ---
@app.route('/')
def index():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, table_number, capacity, location FROM tables ORDER BY table_number")
    tables_data = cur.fetchall()
    cur.close()
    time_slots = get_available_time_slots()
    min_date = datetime.now().strftime('%Y-%m-%d')
    max_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    return render_template('index.html', tables=tables_data, time_slots=time_slots, min_date=min_date, max_date=max_date)

# --- 用户认证 ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        phone_number = request.form.get('phone_number', '')
        hashed_password = generate_password_hash(password)
        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO users (username, email, password_hash, phone_number) VALUES (%s, %s, %s, %s)",
                        (username, email, hashed_password, phone_number))
            mysql.connection.commit()
            flash('注册成功！请登录。', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            mysql.connection.rollback()
            flash(f'注册失败: 用户名或邮箱已存在。', 'danger')
        finally:
            cur.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            session['cart'] = {} # 初始化购物车
            flash('登录成功！', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误。', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('您已成功退出。', 'info')
    return redirect(url_for('index'))

# --- 预约管理 ---
@app.route('/make_reservation', methods=['POST'])
@login_required
def make_reservation():
    user_id = session['user_id']
    table_id = request.form['table_id']
    reservation_date_str = request.form['reservation_date']
    reservation_time_str = request.form['reservation_time']
    num_guests = int(request.form['num_guests'])
    special_requests = request.form.get('special_requests', '')
    try:
        reservation_date = datetime.strptime(reservation_date_str, '%Y-%m-%d').date()
        reservation_time = datetime.strptime(reservation_time_str, '%H:%M').time()
    except ValueError:
        flash('日期或时间格式不正确。', 'danger')
        return redirect(url_for('index'))
    cur = mysql.connection.cursor()
    cur.execute("SELECT capacity FROM tables WHERE id = %s", (table_id,))
    table = cur.fetchone()
    if not table or num_guests > table['capacity']:
        flash('人数超过桌子容量或桌子不存在。', 'danger')
        cur.close()
        return redirect(url_for('index'))
    query_check = "SELECT id FROM reservations WHERE table_id = %s AND reservation_date = %s AND reservation_time = %s AND status != 'cancelled'"
    cur.execute(query_check, (table_id, reservation_date, reservation_time))
    if cur.fetchone():
        flash('该桌子在选定时间已被预订。', 'warning')
        cur.close()
        return redirect(url_for('index'))
    try:
        cur.execute("INSERT INTO reservations (user_id, table_id, reservation_date, reservation_time, num_guests, special_requests) VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, table_id, reservation_date, reservation_time, num_guests, special_requests))
        mysql.connection.commit()
        flash('预约成功！', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'预约失败: {e}', 'danger')
    finally:
        cur.close()
    return redirect(url_for('my_reservations'))

@app.route('/my_reservations')
@login_required
def my_reservations():
    user_id = session['user_id']
    cur = mysql.connection.cursor()
    query = """
        SELECT r.id, t.table_number, t.location, r.reservation_date, r.reservation_time, r.num_guests, r.status
        FROM reservations r JOIN tables t ON r.table_id = t.id
        WHERE r.user_id = %s AND r.status != 'cancelled'
        ORDER BY r.reservation_date DESC, r.reservation_time DESC
    """
    cur.execute(query, (user_id,))
    reservations = cur.fetchall()
    cur.close()
    return render_template('my_reservations.html', reservations=reservations)

@app.route('/cancel_reservation/<int:reservation_id>', methods=['POST'])
@login_required
def cancel_reservation(reservation_id):
    user_id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute("SELECT user_id FROM reservations WHERE id = %s", (reservation_id,))
    reservation = cur.fetchone()
    is_admin = session.get('is_admin', False)
    if (reservation and reservation['user_id'] == user_id) or is_admin:
        try:
            cur.execute("UPDATE reservations SET status = 'cancelled' WHERE id = %s", (reservation_id,))
            mysql.connection.commit()
            flash('预约已取消。', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash(f'取消失败: {e}', 'danger')
    else:
        flash('无权操作。', 'danger')
    cur.close()
    return redirect(request.referrer or url_for('index'))

# --- 菜单和点餐 ---
@app.route('/menu')
def menu():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM menu_categories ORDER BY id")
    categories = cur.fetchall()
    menu_by_category = []
    for category in categories:
        cur.execute("SELECT * FROM menu_items WHERE category_id = %s AND is_available = TRUE ORDER BY name", (category['id'],))
        items = cur.fetchall()
        menu_by_category.append({'id': category['id'], 'name': category['name'], 'description': category['description'], 'items': items})
    cur.close()
    return render_template('menu.html', menu_by_category=menu_by_category)

@app.route('/cart/add/<int:item_id>', methods=['POST'])
@login_required
def add_to_cart(item_id):
    cart = session.get('cart', {})
    quantity = int(request.form.get('quantity', 1))
    item_id_str = str(item_id)
    current_quantity = cart.get(item_id_str, 0)
    cart[item_id_str] = current_quantity + quantity
    session['cart'] = cart
    flash('已加入购物车!', 'success')
    return redirect(request.referrer or url_for('menu'))

@app.route('/cart/remove/<int:item_id>')
@login_required
def remove_from_cart(item_id):
    cart = session.get('cart', {})
    if str(item_id) in cart:
        del cart[str(item_id)]
    session['cart'] = cart
    return redirect(url_for('view_cart'))

@app.route('/cart/clear')
@login_required
def clear_cart():
    session['cart'] = {}
    return redirect(url_for('view_cart'))

@app.route('/cart')
@login_required
def view_cart():
    cart = session.get('cart', {})
    if not cart:
        return render_template('cart.html')

    item_ids = list(cart.keys())
    cur = mysql.connection.cursor()
    format_strings = ','.join(['%s'] * len(item_ids))
    cur.execute(f"SELECT id, name, price FROM menu_items WHERE id IN ({format_strings})", tuple(item_ids))
    items_in_db = cur.fetchall()
    
    cart_items = []
    total_price = 0
    for item in items_in_db:
        item_id_str = str(item['id'])
        quantity = cart[item_id_str]
        cart_items.append({**item, 'quantity': quantity})
        total_price += item['price'] * quantity
        
    cur.execute("SELECT r.id, r.reservation_date, r.reservation_time, t.table_number FROM reservations r JOIN tables t ON r.table_id = t.id WHERE r.user_id = %s AND r.status = 'confirmed' AND r.reservation_date >= CURDATE() ORDER BY r.reservation_date, r.reservation_time", (session['user_id'],))
    user_reservations = cur.fetchall()
    cur.close()
    return render_template('cart.html', cart_items=cart_items, total_price=total_price, user_reservations=user_reservations)

@app.route('/order/place', methods=['POST'])
@login_required
def place_order():
    cart = session.get('cart', {})
    if not cart:
        flash('购物车是空的。', 'warning')
        return redirect(url_for('view_cart'))

    item_ids = list(cart.keys())
    cur = mysql.connection.cursor()
    format_strings = ','.join(['%s'] * len(item_ids))
    cur.execute(f"SELECT id, price FROM menu_items WHERE id IN ({format_strings})", tuple(item_ids))
    items_in_db = {str(item['id']): item for item in cur.fetchall()}

    total_amount = 0
    order_items_to_insert = []
    for item_id_str, quantity in cart.items():
        if item_id_str in items_in_db:
            price = items_in_db[item_id_str]['price']
            total_amount += price * quantity
            order_items_to_insert.append((int(item_id_str), quantity, price))

    try:
        reservation_id = request.form.get('reservation_id')
        reservation_id = int(reservation_id) if reservation_id and reservation_id.isdigit() else None
        
        cur.execute("INSERT INTO orders (user_id, reservation_id, total_amount) VALUES (%s, %s, %s)",
                    (session['user_id'], reservation_id, total_amount))
        order_id = cur.lastrowid
        
        # 使用 executemany 进行批量插入，更安全高效
        order_items_data = []
        for item_id, quantity, price in order_items_to_insert:
            order_items_data.append((order_id, item_id, quantity, price))
        
        if order_items_data:
            cur.executemany("INSERT INTO order_items (order_id, item_id, quantity, price_per_item) VALUES (%s, %s, %s, %s)", order_items_data)
        
        mysql.connection.commit()
        session['cart'] = {}
        flash('下单成功！', 'success')
        return redirect(url_for('my_orders'))
    except Exception as e:
        mysql.connection.rollback()
        app.logger.error(f"Order placement error: {e}")
        flash(f'下单失败: 发生了一个错误。', 'danger')
        return redirect(url_for('view_cart'))
    finally:
        cur.close()

@app.route('/my_orders')
@login_required
def my_orders():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM orders WHERE user_id = %s ORDER BY order_time DESC", (session['user_id'],))
    orders = cur.fetchall()
    cur.close()
    return render_template('my_orders.html', orders=orders)

@app.route('/order/<int:order_id>')
@login_required
def order_details(order_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    order = cur.fetchone()

    is_admin = session.get('is_admin', False)
    if not order or (order['user_id'] != session['user_id'] and not is_admin):
        flash('无权查看此订单。', 'danger')
        return redirect(url_for('my_orders'))

    cur.execute("""
        SELECT oi.quantity, oi.price_per_item, mi.name
        FROM order_items oi JOIN menu_items mi ON oi.item_id = mi.id
        WHERE oi.order_id = %s
    """, (order_id,))
    items = cur.fetchall()
    cur.close()
    
    admin_view = request.args.get('admin_view', type=bool, default=False)
    return render_template('order_details.html', order=order, items=items, admin_view=admin_view)

# --- 管理员路由 ---
@app.route('/admin/reservations')
@admin_required
def admin_reservations():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT r.id, u.username, t.table_number, r.reservation_date, r.reservation_time, r.num_guests, r.status
        FROM reservations r JOIN users u ON r.user_id = u.id JOIN tables t ON r.table_id = t.id
        ORDER BY r.reservation_date DESC, r.reservation_time DESC
    """)
    reservations = cur.fetchall()
    cur.close()
    return render_template('admin_reservations.html', reservations=reservations)

@app.route('/admin/tables', methods=['GET', 'POST'])
@admin_required
def admin_manage_tables():
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'add':
                cur.execute("INSERT INTO tables (table_number, capacity, location) VALUES (%s, %s, %s)",
                            (request.form['table_number'], int(request.form['capacity']), request.form.get('location', '')))
                flash('桌子添加成功!', 'success')
            elif action == 'delete':
                cur.execute("DELETE FROM tables WHERE id = %s", (request.form['table_id'],))
                flash('桌子删除成功!', 'success')
            mysql.connection.commit()
        except Exception as e:
            mysql.connection.rollback()
            flash(f'操作失败: {e}', 'danger')
        finally:
            cur.close()
        return redirect(url_for('admin_manage_tables'))
    
    cur.execute("SELECT * FROM tables ORDER BY table_number")
    tables_data = cur.fetchall()
    cur.close()
    return render_template('admin_tables.html', tables=tables_data)

@app.route('/admin/menu', methods=['GET', 'POST'])
@admin_required
def admin_manage_menu():
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'add_category':
                cur.execute("INSERT INTO menu_categories (name, description) VALUES (%s, %s)",
                            (request.form['name'], request.form.get('description', '')))
                flash('分类添加成功!', 'success')
            elif action == 'add_item':
                is_available = 'is_available' in request.form
                cur.execute("INSERT INTO menu_items (name, description, price, category_id, is_available) VALUES (%s, %s, %s, %s, %s)",
                            (request.form['name'], request.form.get('description', ''), request.form['price'], request.form['category_id'], is_available))
                flash('菜品添加成功!', 'success')
            elif action == 'delete_item':
                cur.execute("DELETE FROM menu_items WHERE id = %s", (request.form['item_id'],))
                flash('菜品删除成功!', 'success')
            mysql.connection.commit()
        except Exception as e:
            mysql.connection.rollback()
            flash(f'操作失败: {e}', 'danger')
        finally:
            cur.close()
        return redirect(url_for('admin_manage_menu'))

    cur.execute("SELECT * FROM menu_categories ORDER BY name")
    categories = cur.fetchall()
    cur.execute("""
        SELECT mi.*, mc.name as category_name FROM menu_items mi
        JOIN menu_categories mc ON mi.category_id = mc.id
        ORDER BY mi.id DESC
    """)
    items = cur.fetchall()
    cur.close()
    return render_template('admin_manage_menu.html', categories=categories, items=items)

@app.route('/admin/orders')
@admin_required
def admin_orders():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT o.*, u.username FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.order_time DESC
    """)
    orders = cur.fetchall()
    cur.close()
    return render_template('admin_orders.html', orders=orders)

@app.route('/admin/order/status/<int:order_id>', methods=['POST'])
@admin_required
def update_order_status(order_id):
    new_status = request.form['status']
    cur = mysql.connection.cursor()
    try:
        cur.execute("UPDATE orders SET status = %s WHERE id = %s", (new_status, order_id))
        mysql.connection.commit()
        flash(f'订单 #{order_id} 状态已更新为 {new_status}', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'更新失败: {e}', 'danger')
    finally:
        cur.close()
    return redirect(url_for('admin_orders'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
