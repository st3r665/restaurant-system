-- 删除旧表 (如果存在)，顺序很重要，先删有外键的
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS reservations;
DROP TABLE IF EXISTS menu_items;
DROP TABLE IF EXISTS menu_categories;
DROP TABLE IF EXISTS tables;
DROP TABLE IF EXISTS users;

-- 用户表
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone_number VARCHAR(20),
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 餐桌表
CREATE TABLE tables (
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_number VARCHAR(10) UNIQUE NOT NULL,
    capacity INT NOT NULL,
    location VARCHAR(100) -- e.g., 'Window side', 'Near kitchen'
);

-- 预约表
CREATE TABLE reservations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    table_id INT NOT NULL,
    reservation_date DATE NOT NULL,
    reservation_time TIME NOT NULL,
    num_guests INT NOT NULL,
    status VARCHAR(20) DEFAULT 'confirmed', -- confirmed, cancelled, completed
    special_requests TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (table_id) REFERENCES tables(id) ON DELETE CASCADE
);

-- 新增：菜单分类表
CREATE TABLE menu_categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT
);

-- 新增：菜单项/菜品表
CREATE TABLE menu_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    image_url VARCHAR(255),
    is_available BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (category_id) REFERENCES menu_categories(id) ON DELETE CASCADE
);

-- 新增：订单表
CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    reservation_id INT, -- 可以是NULL，支持非预约的点餐
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, preparing, completed, paid, cancelled
    order_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (reservation_id) REFERENCES reservations(id) ON DELETE SET NULL
);

-- 新增：订单详情表 (连接订单和菜品)
CREATE TABLE order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    item_id INT NOT NULL,
    quantity INT NOT NULL,
    price_per_item DECIMAL(10, 2) NOT NULL, -- 记录下单时的价格
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES menu_items(id) ON DELETE CASCADE
);


-- 插入示例数据
INSERT INTO users (username, password_hash, email, is_admin) VALUES
('admin', 'pbkdf2:sha256:600000$QyigkYDn9N2aG8vL$c7a95047893a02a0a20a325d3e4141d2f78316c87e838634e0691e469446d4a8', 'admin@example.com', TRUE), -- 密码是 'adminpass'
('testuser', 'pbkdf2:sha256:600000$sKlpQ0zJ1F2gH9iY$099f7e1dd1a7b98868a3030a89704c324a45b96a7a37a4329e9b4b8f8e9a1c2d', 'user@example.com', FALSE); -- 密码是 'userpass'

INSERT INTO tables (table_number, capacity, location) VALUES
('T1', 2, 'Window'),
('T2', 4, 'Center'),
('T3', 4, 'Booth'),
('T4', 6, 'Patio'),
('T5', 2, 'Bar');

-- 插入示例菜单分类
INSERT INTO menu_categories (name, description) VALUES
('主菜', '丰盛的主菜，满足您的味蕾'),
('饮品', '各式冷热饮品'),
('甜点', '为您的美餐画上完美句号');

-- 插入示例菜品
INSERT INTO menu_items (category_id, name, price, description) VALUES
(1, '经典菲力牛排', 158.00, '精选牛里脊，配红酒汁'),
(1, '香煎三文鱼', 128.00, '新鲜三文鱼柳，配柠檬黄油汁'),
(1, '奶油蘑菇意面', 78.00, '浓郁的奶油蘑菇酱汁搭配意面'),
(2, '可口可乐', 10.00, '经典碳酸饮料'),
(2, '鲜榨橙汁', 25.00, '新鲜橙子鲜榨'),
(3, '提拉米苏', 48.00, '经典意大利甜点');

