import sqlite3

DB_NAME = "usta_bot.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            full_name TEXT,
            username TEXT,
            phone TEXT,
            role TEXT,
            city TEXT,
            district TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS masters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            service TEXT NOT NULL,
            description TEXT,
            price TEXT,
            experience INTEGER DEFAULT 0,
            rating REAL DEFAULT 0,
            reviews_count INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            master_id INTEGER,
            service TEXT NOT NULL,
            description TEXT,
            address TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES users(id),
            FOREIGN KEY (master_id) REFERENCES masters(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            master_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def add_user(
    telegram_id,
    full_name,
    username=None,
    phone=None,
    role=None,
    city=None,
    district=None
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO users (
            telegram_id,
            full_name,
            username,
            phone,
            role,
            city,
            district
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(telegram_id)
        DO UPDATE SET
            full_name = excluded.full_name,
            username = excluded.username,
            phone = COALESCE(excluded.phone, users.phone),
            role = COALESCE(excluded.role, users.role),
            city = COALESCE(excluded.city, users.city),
            district = COALESCE(excluded.district, users.district)
    """, (
        telegram_id,
        full_name,
        username,
        phone,
        role,
        city,
        district
    ))

    conn.commit()

    cursor.execute(
        "SELECT * FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )

    user = cursor.fetchone()

    conn.close()

    return user


def get_user(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )

    user = cursor.fetchone()

    conn.close()

    return user


def add_master(
    telegram_id,
    service,
    description,
    price,
    experience
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )

    user = cursor.fetchone()

    if not user:
        conn.close()
        return False

    cursor.execute("""
        INSERT INTO masters (
            user_id,
            service,
            description,
            price,
            experience
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            service = excluded.service,
            description = excluded.description,
            price = excluded.price,
            experience = excluded.experience
    """, (
        user["id"],
        service,
        description,
        price,
        experience
    ))

    conn.commit()
    conn.close()

    return True


def find_masters(service, city=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            masters.*,
            users.telegram_id,
            users.full_name,
            users.username,
            users.phone,
            users.city,
            users.district
        FROM masters
        JOIN users ON masters.user_id = users.id
        WHERE masters.service LIKE ?
    """

    params = [f"%{service}%"]

    if city:
        query += " AND users.city LIKE ?"
        params.append(f"%{city}%")

    query += " ORDER BY masters.rating DESC"

    cursor.execute(query, params)

    masters = cursor.fetchall()

    conn.close()

    return masters


def create_order(
    customer_telegram_id,
    service,
    description,
    address
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE telegram_id = ?",
        (customer_telegram_id,)
    )

    customer = cursor.fetchone()

    if not customer:
        conn.close()
        return None

    cursor.execute("""
        INSERT INTO orders (
            customer_id,
            service,
            description,
            address
        )
        VALUES (?, ?, ?, ?)
    """, (
        customer["id"],
        service,
        description,
        address
    ))

    order_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return order_id


def get_new_orders():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            orders.*,
            users.telegram_id,
            users.full_name,
            users.phone
        FROM orders
        JOIN users ON orders.customer_id = users.id
        WHERE orders.status = 'new'
        ORDER BY orders.id DESC
    """)

    orders = cursor.fetchall()

    conn.close()

    return orders


def assign_order(order_id, master_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE orders
        SET master_id = ?, status = 'accepted'
        WHERE id = ? AND status = 'new'
    """, (master_id, order_id))

    conn.commit()

    success = cursor.rowcount > 0

    conn.close()

    return success


def get_master_by_telegram_id(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            masters.*,
            users.telegram_id,
            users.full_name,
            users.phone,
            users.city,
            users.district
        FROM masters
        JOIN users ON masters.user_id = users.id
        WHERE users.telegram_id = ?
    """, (telegram_id,))

    master = cursor.fetchone()

    conn.close()

    return master


def get_statistics():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM masters")
    masters_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders")
    orders_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM orders
        WHERE status = 'accepted'
    """)
    accepted_orders = cursor.fetchone()[0]

    conn.close()

    return {
        "users": users_count,
        "masters": masters_count,
        "orders": orders_count,
        "accepted_orders": accepted_orders
    }
