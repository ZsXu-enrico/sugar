from flask import Blueprint, render_template, request, jsonify,flash,redirect,url_for
from werkzeug.security import check_password_hash
from .database import Database
import pymysql
from datetime import datetime
import uuid
# 创建一个 Blueprint 对象
main_views = Blueprint('main', __name__)

@main_views.route('/')
def index():
    return render_template('index.html')

@main_views.route('/login', methods=['POST'])
def login():
    data = request.json
    customer_id = data.get('CustomerID')
    password = data.get('Password')

    if not customer_id or not password:
        return jsonify({"message": "Missing data"}), 400

    db = Database()
    conn = db.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        cursor.execute("SELECT * FROM customers WHERE CustomerID = %s", (customer_id,))
        customer = cursor.fetchone()
        if customer and check_password_hash(customer['Password'], password):
            return jsonify({"message": "Login successful", "customer_id": customer_id})
        else:
            return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"message": "Error logging in", "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@main_views.route('/customer/info', methods=['GET'])
def get_customer_info():
    customer_id = request.args.get('customer_id')
    password = request.args.get('password')  # 获取URL参数中的密码

    if not customer_id or not password:  # 检查是否提供了customer_id和password
        return jsonify({"message": "Missing customer_id or password"}), 400

    db = Database()
    conn = db.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        cursor.execute("SELECT * FROM customers WHERE CustomerID = %s", (customer_id,))
        customer = cursor.fetchone()
        if customer and check_password_hash(customer['Password'], password):  # 验证密码
            # 确保不返回密码信息
            customer.pop('Password', None)
            cursor.execute("SELECT * FROM viewcustomerorders WHERE CustomerID = %s", (customer_id,))
            orders = cursor.fetchall()
            return jsonify({"customer": customer, "orders": orders})
        else:
            return jsonify({"message": "Invalid customer_id or password"}), 401
    except Exception as e:
        return jsonify({"message": "Error retrieving customer info", "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
@main_views.route('/books', methods=['GET'])
def search_books():
    isbn = request.args.get('isbn')
    title = request.args.get('title')
    publisher_name = request.args.get('publisher')
    keywords = request.args.get('keywords')
    author_name = request.args.get('author')

    db = Database()
    conn = db.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

   
    query = """
        SELECT 
            b.ISBN, b.Title, p.PublisherName, b.Price, b.Keywords, b.StockQuantity,
            a.AuthorName AS Authors
        FROM books b
        LEFT JOIN publishers p ON b.PublisherID = p.PublisherID
        LEFT JOIN book_authors ba ON b.ISBN = ba.BookISBN
        LEFT JOIN authors a ON ba.AuthorID = a.AuthorID
    """
    conditions = []
    params = []

    if isbn:
        conditions.append("b.ISBN = %s")
        params.append(isbn)
    if title:
        conditions.append("b.Title LIKE %s")
        params.append(f"%{title}%")
    if publisher_name:
        conditions.append("p.PublisherName = %s")
        params.append(publisher_name)
    if keywords:
        conditions.append("b.Keywords LIKE %s")
        params.append(f"%{keywords}%")
    if author_name:
        conditions.append("a.AuthorName LIKE %s")
        params.append(f"%{author_name}%")

    if conditions:
        query += " AND " + " AND ".join(conditions)

    try:
        cursor.execute(query, tuple(params))
        books = cursor.fetchall()
        return jsonify(books)
    except Exception as e:
        return jsonify({"message": "Error searching books", "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@main_views.route('/admin')
def admin():
    # 这里可以添加管理员登录验证逻辑
    return render_template('admin.html')  # 渲染管理员界面模板


@main_views.route('/admin/books', methods=['GET', 'POST'])
def manage_books():
    db = Database()
    conn = db.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    if request.method == 'POST':
        # 获取表单数据
        title = request.form.get('title')
        authors = request.form.get('authors').split(',')  # 假设作者字段以逗号分隔
        publisher_name = request.form.get('publisher')  # 获取出版社名称
        price = request.form.get('price')
        keywords = request.form.get('keywords').split(',')  # 假设关键字字段以逗号分隔
        summary = request.form.get('summary')
        cover_image_file = request.files.get('cover_image')  # 获取文件对象
        stock_quantity = request.form.get('stock_quantity')
        suppliers = request.form.get('supplier').split(',')  # 假设供应商字段以逗号分隔
        
        # 数据验证
        if not all([title, price]):
            flash('标题和价格是必填字段。')
            return redirect(url_for('main.manage_books'))
        
        try:
            # 首先，获取出版社ID
            cursor.execute("SELECT PublisherID FROM publishers WHERE PublisherName = %s", (publisher_name,))
            publisher_id = cursor.fetchone()
            if not publisher_id:
                raise ValueError("未找到出版社。")

            # 插入书籍信息到数据库（不包括ISBN，因为它是自增的）
            cursor.execute("INSERT INTO books (Title, PublisherID, Price, Keywords, Summary, StockQuantity) VALUES (%s, %s, %s, %s, %s, %s)", (title, publisher_id['PublisherID'], price, ','.join(keywords), summary, stock_quantity))
            conn.commit()
            
            # 获取自增的ISBN
            last_inserted_isbn = cursor.lastrowid
            
            # 处理作者关系
            for author in authors:
                cursor.execute("INSERT INTO authors (AuthorName) VALUES (%s)", (author,))
                conn.commit()
                author_id = cursor.lastrowid
                cursor.execute("INSERT INTO book_authors (BookISBN, AuthorID) VALUES (%s, %s)", (last_inserted_isbn, author_id))
                conn.commit()
            
            # 处理供应商关系
            for supplier_name in suppliers:
                cursor.execute("SELECT SupplierID FROM suppliers WHERE SupplierName = %s", (supplier_name,))
                supplier_id = cursor.fetchone()
                if supplier_id:
                    cursor.execute("INSERT INTO book_suppliers (BookISBN, SupplierID) VALUES (%s, %s)", (last_inserted_isbn, supplier_id['SupplierID']))
                    conn.commit()
                else:
                    cursor.execute("INSERT INTO suppliers (SupplierName) VALUES (%s)", (supplier_name,))
                    conn.commit()
                    supplier_id = cursor.lastrowid
                    cursor.execute("INSERT INTO book_suppliers (BookISBN, SupplierID) VALUES (%s, %s)", (last_inserted_isbn, supplier_id))
                    conn.commit()
            
            flash('新书添加成功！')
        except (pymysql.MySQLError, ValueError) as e:
            conn.rollback()
            flash('添加新书失败：' + str(e))
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('main.manage_books'))
    
    # 查询所有图书信息
    try:
        cursor.execute("SELECT b.ISBN, b.Title, p.PublisherName, b.Price, b.Keywords, b.StockQuantity, a.AuthorName AS Authors FROM books b LEFT JOIN publishers p ON b.PublisherID = p.PublisherID LEFT JOIN book_authors ba ON b.ISBN = ba.BookISBN LEFT JOIN authors a ON ba.AuthorID = a.AuthorID")
        books = cursor.fetchall()
    except pymysql.MySQLError as e:
        flash('查询图书信息失败：' + str(e))
        return redirect(url_for('main.manage_books'))
    finally:
        cursor.close()
        conn.close()

    return render_template('admin_books.html', books=books)

@main_views.route('/admin/missingBook')
def missing_book():
    return render_template('missingBook.html')

@main_views.route('/api/missingbooks', methods=['POST'])
def register_missing_book():
    db = Database()
    data = request.json
    isbn = data.get('isbn')
    title = data.get('title')
    publisher = data.get('publisher')
    supplier = data.get('supplier')
    quantity = data.get('quantity')

    try:
        conn = db.connect()
        with conn.cursor() as cursor:
            query = """
                INSERT INTO missingbooks (ISBN, Title, PublisherID, SupplierID, Quantity, Register_Date)
                VALUES (%s, %s, %s, %s, %s, CURDATE())
            """
            cursor.execute(query, (isbn, title, publisher, supplier, quantity))
            conn.commit()
        return jsonify({"success": True, "message": "登记成功", "data": data})
    except Exception as e:
        return jsonify({"success": False, "message": "登记失败，请重试", "error": str(e)}), 500
    finally:
        conn.close()

@main_views.route('/admin/users', methods=['GET'])
def admin_customer():
    return render_template('admin_customers.html')

@main_views.route('/get_customer_info', methods=['GET'])
def customer_info():
    customer_id = request.args.get('customer_id')
    if not customer_id:
        return jsonify({"message": "Missing customer_id"}), 400

    db = Database()
    conn = db.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        # 查询客户信息
        cursor.execute("SELECT * FROM customers WHERE CustomerID = %s", (customer_id,))
        customer = cursor.fetchone()
        if not customer:
            return jsonify({"message": "Customer not found"}), 404

        # 查询订单信息
        cursor.execute("SELECT * FROM orders WHERE CustomerID = %s", (customer_id,))
        orders = cursor.fetchall()

        # 返回客户信息和订单信息
        return jsonify({"customer": customer, "orders": orders})
    except Exception as e:
        # 捕获异常并返回详细的错误信息
        error_message = f"Error retrieving customer info: {str(e)}"
        return jsonify({"message": error_message}), 500
    finally:
        cursor.close()
        conn.close()

@main_views.route('/place_order_form', methods=['GET'])
def place_order_form():
    return render_template('order_form.html')

@main_views.route('/place_order', methods=['POST'])
def place_order():
    customer_id = request.form.get('customer_id')
    # 假设前端发送的格式为 "123,456,789"，逗号分隔不同的ISBN
    isbns_data = request.form.get('books')  # ISBN 数据，例如 "123,456,789"
    quantity = int(request.form.get('quantity'))  # 单独的数量
    shipping_address = request.form.get('shipping_address')

    # 处理 ISBN 数据，分割字符串
    isbns = isbns_data.split(',')
    books = [{'isbn': isbn, 'quantity': quantity} for isbn in isbns]

    # 计算总金额和检查库存的逻辑
    order_date = datetime.now().strftime('%Y-%m-%d')
    total_amount = 0
    db = Database()
    conn = db.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    for book in books:
        cursor.execute("SELECT Price FROM books WHERE ISBN = %s", (book['isbn'],))
        book_price = cursor.fetchone()
        if book_price and 'Price' in book_price:
            total_amount += book_price['Price'] * book['quantity']
            cursor.execute("INSERT INTO orderdetails (OrderID, ISBN, Quantity, PriceAtOrder) VALUES (NULL, %s, %s, %s)", (book['isbn'], book['quantity'], book_price['Price']))
        else:
            flash(f"未找到ISBN为{book['isbn']}的书籍或书籍价格。")
            continue  # 如果书籍信息无效，跳过这本书，继续处理下一本

    # 如果总金额为0，可能是由于书籍信息无效或库存不足
    if total_amount == 0:
        flash("订单未能创建，因为所有书籍信息无效或库存不足。")
        return redirect(url_for('place_order_form'))  # 假设有一个表单页面

    # 插入订单信息到数据库，不包括自增的OrderID
    cursor.execute("""
        INSERT INTO orders (OrderDate, CustomerID, ShippingAddress, TotalAmount, ShippingStatus) 
        VALUES (%s, %s, %s, %s, %s)
    """, (order_date, customer_id, shipping_address, total_amount, '未发货'))
    conn.commit()
    order_id = cursor.lastrowid  # 获取数据库生成的自增ID
    cursor.close()
    conn.close()

    # 重定向到订单确认页面
    return render_template('order_confirmation.html', 
                           order_id=order_id, 
                           order_date=order_date, 
                           customer_id=customer_id, 
                           total_amount=total_amount, 
                           shipping_address=shipping_address)

@main_views.route('/admin/orders')
def show_orders():
    db = Database()
    conn = db.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        cursor.execute("SELECT * FROM orders")
        orders = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template('admin_orders.html', orders=orders)

@main_views.route('/admin/update_order_status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    db = Database()
    conn = db.connect()
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE orders SET ShippingStatus = '已发货' WHERE OrderID = %s", (order_id,))
        conn.commit()
    except Exception as e:
        # 记录异常信息
        print(e)
        return jsonify({"message": "Failed to update order status", "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('main.show_orders'))

@main_views.route('/customer-info/<customer_id>')
def show_customer_info(customer_id):  # 重命名函数
    # 这里可以添加管理员登录验证逻辑
    try:
        db = Database()
        conn = db.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        cursor.execute("SELECT * FROM customers WHERE CustomerID = %s", (customer_id,))
        customer = cursor.fetchone()
        if not customer:
            return jsonify({"message": "Customer not found"}), 404

        cursor.execute("SELECT * FROM orders WHERE CustomerID = %s", (customer_id,))
        orders = cursor.fetchall()

        return render_template('customer_info.html', customer=customer, orders=orders)
    except Exception as e:
        return jsonify({"message": "Error retrieving customer info", "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()