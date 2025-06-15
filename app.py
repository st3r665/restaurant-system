# app.py
import os
from datetime import datetime, timedelta, time
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from datetime import datetime, timedelta, time, date

app = Flask(__name__)

# --- 配置 ---
app.secret_key = os.urandom(24) # 用于session加密

# MySQL配置 (请根据你的MySQL设置修改)
app.config['MYSQL_HOST'] = '192.168.56.131'
app.config['MYSQL_USER'] = 'star' # 替换为你的MySQL用户名
app.config['MYSQL_PASSWORD'] = 'Xsy_041207' # 替换为你的MySQL密码
app.config['MYSQL_DB'] = 'restaurant_db'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor' # 返回字典形式的结果

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
    """生成餐厅的可用时间段 (例如: 10:00 - 22:00, 每小时一个slot)"""
    slots = []
    start_hour = 10
    end_hour = 22 # 最后一个可预约时间是21:00，持续到22:00
    current_time = datetime.now().time()
    today = datetime.now().date()

    for hour in range(start_hour, end_hour):
        slot_time = time(hour, 0)
        # 如果是今天，只显示未来的时间段
        # (这里简化，实际可能需要更复杂的逻辑，比如提前多久不能预约)
        # if date_obj == today and slot_time <= current_time:
        #     continue
        slots.append(slot_time.strftime('%H:%M'))
    return slots

# --- 路由 ---
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow}
@app.route('/')
def index():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, table_number, capacity, location FROM tables ORDER BY table_number")
    tables_data = cur.fetchall()
    cur.close()
    time_slots = get_available_time_slots()
    min_date = (datetime.now()).strftime('%Y-%m-%d')
    max_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d') # 最多提前30天预约

    return render_template('index.html', tables=tables_data, time_slots=time_slots, min_date=min_date, max_date=max_date)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        phone_number = request.form.get('phone_number', '') # 可选

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
            if 'UNIQUE constraint failed' in str(e) or 'Duplicate entry' in str(e): # SQLite / MySQL
                 flash('用户名或邮箱已存在。', 'danger')
            else:
                flash(f'注册失败: {str(e)}', 'danger')
            app.logger.error(f"Registration error: {e}")
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
            flash('登录成功！', 'success')
            if user['is_admin']:
                return redirect(url_for('admin_reservations'))
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

    # 1. 检查桌子容量
    cur = mysql.connection.cursor()
    cur.execute("SELECT capacity FROM tables WHERE id = %s", (table_id,))
    table = cur.fetchone()
    if not table:
        flash('所选桌子不存在。', 'danger')
        cur.close()
        return redirect(url_for('index'))
    if num_guests > table['capacity']:
        flash(f'预定人数 ({num_guests}) 超过所选桌子最大容量 ({table["capacity"]})。', 'danger')
        cur.close()
        return redirect(url_for('index'))
    
    # 2. 检查桌子在指定日期和时间是否已被预订
    # 假设一个预约占用1小时，检查该小时内是否有重叠
    # (实际应用中，可能需要更复杂的预约时段逻辑，例如预约持续2小时)
    query_check = """
        SELECT id FROM reservations
        WHERE table_id = %s AND reservation_date = %s AND reservation_time = %s AND status != 'cancelled'
    """
    cur.execute(query_check, (table_id, reservation_date, reservation_time))
    existing_reservation = cur.fetchone()

    if existing_reservation:
        flash('该桌子在选定时间已被预订，请选择其他时间或桌子。', 'warning')
        cur.close()
        return redirect(url_for('index'))

    # 3. 创建预约
    try:
        insert_query = """
            INSERT INTO reservations (user_id, table_id, reservation_date, reservation_time, num_guests, special_requests)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cur.execute(insert_query, (user_id, table_id, reservation_date, reservation_time, num_guests, special_requests))
        mysql.connection.commit()
        flash('预约成功！', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'预约失败: {str(e)}', 'danger')
        app.logger.error(f"Reservation creation error: {e}")
    finally:
        cur.close()

    return redirect(url_for('my_reservations'))


@app.route('/my_reservations')
@login_required
def my_reservations():
    user_id = session['user_id']
    cur = mysql.connection.cursor()
    query = """
        SELECT r.id, t.table_number, t.location, r.reservation_date, r.reservation_time, r.num_guests, r.status, r.special_requests
        FROM reservations r
        JOIN tables t ON r.table_id = t.id
        WHERE r.user_id = %s AND r.status != 'cancelled'
        ORDER BY r.reservation_date DESC, r.reservation_time DESC
    """
    cur.execute(query, (user_id,))
    reservations_data_raw = cur.fetchall()
    cur.close()

    reservations_list = []
    for row_dict in reservations_data_raw:
        processed_row = dict(row_dict) # 创建一个可修改的副本

        # 处理 reservation_date (应为 datetime.date 类型)
        if isinstance(processed_row.get('reservation_date'), date):
            processed_row['reservation_date_str'] = processed_row['reservation_date'].strftime('%Y-%m-%d')
        else:
            processed_row['reservation_date_str'] = str(processed_row.get('reservation_date', 'N/A'))

        # 处理 reservation_time
        rt = processed_row.get('reservation_time')
        if isinstance(rt, time):
            processed_row['reservation_time_str'] = rt.strftime('%H:%M')
        elif isinstance(rt, timedelta):
            # 将 timedelta 转换为 HH:MM 格式 (如果它代表一天内的时间)
            # (datetime.min + timedelta).time() 是一个常用技巧
            try:
                # 确保 timedelta 是正数且在合理范围内
                if rt.total_seconds() >= 0:
                    # 创建一个基准 datetime 对象，加上 timedelta，然后取 time 部分
                    time_val = (datetime.min + rt).time()
                    processed_row['reservation_time_str'] = time_val.strftime('%H:%M')
                else: # 负的 timedelta
                    processed_row['reservation_time_str'] = f"间隔: {str(rt)}" # 或其他错误提示
            except OverflowError: # 如果 timedelta 太大，datetime.min + rt 可能溢出
                 processed_row['reservation_time_str'] = f"超大间隔: {str(rt)}"
        else:
            processed_row['reservation_time_str'] = str(rt if rt is not None else 'N/A')

        reservations_list.append(processed_row)

    return render_template('my_reservations.html', reservations=reservations_list)

@app.route('/cancel_reservation/<int:reservation_id>', methods=['POST'])
@login_required
def cancel_reservation(reservation_id):
    user_id = session['user_id']
    cur = mysql.connection.cursor()

    # 检查预约是否属于当前用户
    cur.execute("SELECT user_id FROM reservations WHERE id = %s", (reservation_id,))
    reservation = cur.fetchone()

    if reservation and reservation['user_id'] == user_id:
        try:
            cur.execute("UPDATE reservations SET status = 'cancelled' WHERE id = %s", (reservation_id,))
            mysql.connection.commit()
            flash('预约已取消。', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash(f'取消预约失败: {str(e)}', 'danger')
            app.logger.error(f"Cancellation error: {e}")
    elif session.get('is_admin'): # 管理员可以取消任何预约
         try:
            cur.execute("UPDATE reservations SET status = 'cancelled' WHERE id = %s", (reservation_id,))
            mysql.connection.commit()
            flash(f'管理员操作：预约 {reservation_id} 已取消。', 'success')
         except Exception as e:
            mysql.connection.rollback()
            flash(f'管理员取消预约失败: {str(e)}', 'danger')
            app.logger.error(f"Admin cancellation error: {e}")
    else:
        flash('您没有权限取消此预约。', 'danger')
    
    cur.close()
    if session.get('is_admin') and request.referrer and 'admin_reservations' in request.referrer:
        return redirect(url_for('admin_reservations'))
    return redirect(url_for('my_reservations'))


# --- 管理员路由 ---
@app.route('/admin/reservations')
@admin_required
def admin_reservations():
    cur = mysql.connection.cursor()
    query = """
        SELECT r.id, u.username, t.table_number, r.reservation_date, r.reservation_time, r.num_guests, r.status, r.special_requests
        FROM reservations r
        JOIN users u ON r.user_id = u.id
        JOIN tables t ON r.table_id = t.id
        ORDER BY r.reservation_date DESC, r.reservation_time DESC
    """
    cur.execute(query)
    reservations_data_raw = cur.fetchall()
    cur.close()

    reservations_list_admin = []
    for row_dict in reservations_data_raw:
        processed_row = dict(row_dict)

        if isinstance(processed_row.get('reservation_date'), date):
            processed_row['reservation_date_str'] = processed_row['reservation_date'].strftime('%Y-%m-%d')
        else:
            processed_row['reservation_date_str'] = str(processed_row.get('reservation_date', 'N/A'))

        rt = processed_row.get('reservation_time')
        if isinstance(rt, time):
            processed_row['reservation_time_str'] = rt.strftime('%H:%M')
        elif isinstance(rt, timedelta):
            try:
                if rt.total_seconds() >= 0:
                    time_val = (datetime.min + rt).time()
                    processed_row['reservation_time_str'] = time_val.strftime('%H:%M')
                else:
                    processed_row['reservation_time_str'] = f"间隔: {str(rt)}"
            except OverflowError:
                 processed_row['reservation_time_str'] = f"超大间隔: {str(rt)}"
        else:
            processed_row['reservation_time_str'] = str(rt if rt is not None else 'N/A')
        
        reservations_list_admin.append(processed_row)

    return render_template('admin_reservations.html', reservations=reservations_list_admin)

# 如果需要管理桌子，可以添加以下路由 (示例)
@app.route('/admin/tables', methods=['GET', 'POST'])
@admin_required
def admin_manage_tables():
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            table_number = request.form['table_number']
            capacity = int(request.form['capacity'])
            location = request.form.get('location', '')
            try:
                cur.execute("INSERT INTO tables (table_number, capacity, location) VALUES (%s, %s, %s)",
                            (table_number, capacity, location))
                mysql.connection.commit()
                flash('桌子添加成功!', 'success')
            except Exception as e:
                mysql.connection.rollback()
                flash(f'添加桌子失败: {e}', 'danger')
        elif action == 'delete':
            table_id = request.form['table_id']
            # 注意: 删除桌子前最好检查是否有未完成的预约
            try:
                cur.execute("DELETE FROM tables WHERE id = %s", (table_id,))
                mysql.connection.commit()
                flash('桌子删除成功!', 'success')
            except Exception as e:
                mysql.connection.rollback()
                flash(f'删除桌子失败: {e}', 'danger')
        return redirect(url_for('admin_manage_tables'))

    cur.execute("SELECT id, table_number, capacity, location FROM tables ORDER BY table_number")
    tables_data = cur.fetchall()
    cur.close()
    return render_template('admin_tables.html', tables=tables_data)


if __name__ == '__main__':
    app.run(debug=True)