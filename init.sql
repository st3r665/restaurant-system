DROP TABLE IF EXISTS reservations;
DROP TABLE IF EXISTS tables;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone_number VARCHAR(20),
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tables (
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_number VARCHAR(10) UNIQUE NOT NULL,
    capacity INT NOT NULL,
    location VARCHAR(100) -- e.g., 'Window side', 'Near kitchen'
);

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

INSERT INTO users (username, password_hash, email, is_admin) VALUES
('admin', '$22b00b208f129e22d0b4374b6092aab3472b6b96ef2830dd05c9eeb12451c1c2cb9d65e2c8f112911517a03c7d90f713907a99accee7f72aa77d4869806661d9', 'admin@example.com', TRUE), -- 密码是 'adminpass'
('testuser', 'pbkdf2:sha256:600000$sKlpQ0zJ1F2gH9iY$099f7e1dd1a7b98868a3030a89704c324a45b96a7a37a4329e9b4b8f8e9a1c2d', 'user@example.com', FALSE); -- 密码是 'userpass'


INSERT INTO tables (table_number, capacity, location) VALUES
('T1', 2, 'Window'),
('T2', 4, 'Center'),
('T3', 4, 'Booth'),
('T4', 6, 'Patio'),
('T5', 2, 'Bar');