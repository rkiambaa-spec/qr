import http.server
import socketserver
import json
import sqlite3
import uuid
import qrcode
import io
import base64
from urllib.parse import urlparse, parse_qs
from http.cookies import SimpleCookie
from werkzeug.security import generate_password_hash, check_password_hash

# --- CONFIGURATION & SETUP ---
DB_FILE = "permits.db"
# IMPORTANT: In a real application, use environment variables for secrets.
SECRET_KEY = "a-very-secret-key-for-sessions" 
USERNAME = "admin"
# For simplicity, password is hardcoded. In production, hash it securely.
PASSWORD_HASH = generate_password_hash("Admin@2030$")

def init_db():
    """Initializes the SQLite database and creates the permits table if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Updated table to include all fields from the image
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS permits (
        id TEXT PRIMARY KEY,
        businessName TEXT,
        businessId TEXT,
        addressPoBox TEXT,
        phone TEXT,
        subcounty TEXT,
        ward TEXT,
        market TEXT,
        plotNo TEXT,
        activity TEXT,
        amount TEXT,
        amountInWords TEXT,
        issueDate TEXT,
        expiryDate TEXT,
        status TEXT
    )
    """)
    conn.commit()
    conn.close()

# --- HTML TEMPLATES ---

def get_login_page_template():
    """Returns the HTML for the login page, styled to match the user's image."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login - Murang'a County E-Service Portal</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
        <style>
            body {
                background: linear-gradient(to right, #1e6b42, #6ba54a);
            }
        </style>
    </head>
    <body class="flex justify-center h-screen">
        <div class="w-full max-w-md bg-white p-8 h-screen shadow-2xl text-gray-600 rounded-b-sm">
            <h1 class="text-xl font-semibold text-center mb-1">Murang'a County E-Service Portal</h1>
            <p class="text-sm text-center mb-8">Sign In</p>
            
            <form method="POST" action="/login" class="space-y-6">
                <div class="relative">
                    <i class="fas fa-user absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"></i>
                    <input type="text" name="username" placeholder="Email / Phone Number" class="w-full pl-10 p-2 border-b-2 border-gray-200 focus:outline-none focus:border-green-500" value="">
                </div>
                <div class="relative">
                    <i class="fas fa-lock absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"></i>
                    <input type="password" name="password" placeholder="Password" class="w-full pl-10 p-2 border-b-2 border-gray-200 focus:outline-none focus:border-green-500" value="">
                </div>

                <div>
                    <p class="text-sm mb-2">Select portal you want to log into</p>
                    <div class="space-y-2">
                        <label class="flex items-center">
                            <input type="radio" name="portal" class="form-radio text-green-600">
                            <span class="ml-2">Single Business Permit</span>
                        </label>
                        <label class="flex items-center">
                            <input type="radio" name="portal" class="form-radio text-green-600" checked>
                            <span class="ml-2">Liquor Application</span>
                        </label>
                    </div>
                </div>

                <div class="flex justify-between items-center text-sm">
                    <label class="flex items-center">
                        <input type="checkbox" class="form-checkbox text-green-600">
                        <span class="ml-2">Remember Me</span>
                    </label>
                </div>
                
                <div class="flex justify-between items-center text-sm">
                    <a href="#" class="text-blue-500 hover:underline">Create an account</a>
                    <a href="#" class="text-blue-500 hover:underline">Forgot Password? Get OTP</a>
                </div>

                <button type="submit" class="w-full bg-green-600 text-white p-3 rounded-full hover:bg-green-700 font-bold text-lg transition-transform transform hover:scale-105">
                    Login
                </button>
            </form>
        </div>
    </body>
    </html>
    """

def get_main_page_template(permits_html):
    """Returns the HTML for the main generator and list page."""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Permit Generator</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100 p-4 md:p-8">
        <div class="max-w-4xl mx-auto">
            <div class="flex justify-between items-center mb-4">
                <h1 class="text-3xl font-bold">Permit Dashboard</h1>
                <a href="/logout" class="text-blue-500 hover:underline">Logout</a>
            </div>
            <!-- Form Section -->
            <div class="bg-white p-6 rounded-lg shadow-md mb-8">
                <div class="mb-6">
                    <h2 class="text-3xl font-bold text-gray-800">COUNTY GOVERNMENT OF MURANG'A</h2>
                    <h3 class="text-2xl font-semibold text-gray-700 mt-2">Liquor Permit Verification</h3>
                </div>
                <form action="/" method="POST" class="space-y-3 text-gray-700">
                    <p class="flex flex-col md:flex-row justify-between md:items-center"><span class="font-semibold md:w-1/3 mb-1 md:mb-0">Business Name/ Owner:</span><input type="text" name="businessName" value="" class="w-full md:w-2/3 p-2 border rounded"></p>
                    <p class="flex flex-col md:flex-row justify-between md:items-center"><span class="font-semibold md:w-1/3 mb-1 md:mb-0">Business ID No:</span><input type="text" name="businessId" value="" class="w-full md:w-2/3 p-2 border rounded"></p>
                    <p class="flex flex-col md:flex-row justify-between md:items-center"><span class="font-semibold md:w-1/3 mb-1 md:mb-0">Address P.O. Box:</span><input type="text" name="addressPoBox" value="" class="w-full md:w-2/3 p-2 border rounded"></p>
                    <p class="flex flex-col md:flex-row justify-between md:items-center"><span class="font-semibold md:w-1/3 mb-1 md:mb-0">Phone No.:</span><input type="text" name="phone" value="" class="w-full md:w-2/3 p-2 border rounded"></p>
                    <p class="flex flex-col md:flex-row justify-between md:items-center"><span class="font-semibold md:w-1/3 mb-1 md:mb-0">Subcounty:</span><input type="text" name="subcounty" value="" class="w-full md:w-2/3 p-2 border rounded"></p>
                    <p class="flex flex-col md:flex-row justify-between md:items-center"><span class="font-semibold md:w-1/3 mb-1 md:mb-0">Ward:</span><input type="text" name="ward" value="" class="w-full md:w-2/3 p-2 border rounded"></p>
                    <p class="flex flex-col md:flex-row justify-between md:items-center"><span class="font-semibold md:w-1/3 mb-1 md:mb-0">Market:</span><input type="text" name="market" value="" class="w-full md:w-2/3 p-2 border rounded"></p>
                    <p class="flex flex-col md:flex-row justify-between md:items-center"><span class="font-semibold md:w-1/3 mb-1 md:mb-0">Plot No:</span><input type="text" name="plotNo" value="" class="w-full md:w-2/3 p-2 border rounded"></p>
                    <p class="flex flex-col md:flex-row justify-between md:items-center"><span class="font-semibold md:w-1/3 mb-1 md:mb-0">Activity/Business/Profession or Occupation of:</span><input type="text" name="activity" value="" class="w-full md:w-2/3 p-2 border rounded"></p>
                    <p class="flex flex-col md:flex-row justify-between md:items-center"><span class="font-semibold md:w-1/3 mb-1 md:mb-0">Permit Amount Paid:</span><input type="text" name="amount" value="" class="w-full md:w-2/3 p-2 border rounded"></p>
                    <p class="flex flex-col md:flex-row justify-between md:items-center"><span class="font-semibold md:w-1/3 mb-1 md:mb-0">Kshs in words:</span><input type="text" name="amountInWords" value="" class="w-full md:w-2/3 p-2 border rounded"></p>
                    <p class="flex flex-col md:flex-row justify-between md:items-center"><span class="font-semibold md:w-1/3 mb-1 md:mb-0">Date of issue:</span><input type="text" name="issueDate" value="" class="w-full md:w-2/3 p-2 border rounded"></p>
                    <p class="flex flex-col md:flex-row justify-between md:items-center"><span class="font-semibold md:w-1/3 mb-1 md:mb-0">Expiry Date:</span><input type="text" name="expiryDate" value="" class="w-full md:w-2/3 p-2 border rounded"></p>
                    <p class="flex flex-col md:flex-row justify-between md:items-center"><span class="font-semibold md:w-1/3 mb-1 md:mb-0">Status:</span><input type="text" name="status" value="" class="w-full md:w-2/3 p-2 border rounded"></p>
                    
                    <button type="submit" class="w-full mt-6 bg-blue-600 text-white font-bold py-3 rounded-lg hover:bg-blue-700">
                        Create New Permit
                    </button>
                </form>
            </div>

            <!-- Permit List Section -->
            <div class="bg-white p-6 rounded-lg shadow-md">
                <h2 class="text-2xl font-bold mb-4">Existing Permits</h2>
                <div id="permit-list" class="space-y-4">{permits_html}</div>
            </div>
        </div>
        
        <!-- Modal for QR Code -->
        <div id="qr-modal" class="fixed inset-0 bg-black bg-opacity-50 hidden items-center justify-center p-4">
            <div class="bg-white p-6 rounded-lg text-center">
                <h3 class="text-xl font-semibold mb-4">Permit QR Code</h3>
                <div id="modal-qr-code"></div>
                <button onclick="closeModal()" class="mt-4 bg-gray-500 text-white px-4 py-2 rounded">Close</button>
            </div>
        </div>

        <script>
            function showQrCode(permitId, permitUrl) {{
                const modal = document.getElementById('qr-modal');
                const qrContainer = document.getElementById('modal-qr-code');
                fetch(`/api/qrcode?url=${{encodeURIComponent(permitUrl)}}`)
                    .then(response => response.json())
                    .then(data => {{
                        qrContainer.innerHTML = `<img src="${{data.qr_code_image}}" alt="QR Code for ${{permitId}}">`;
                        modal.style.display = 'flex';
                    }});
            }}
            function closeModal() {{
                document.getElementById('qr-modal').style.display = 'none';
            }}
            function deletePermit(permitId) {{
                if (!confirm('Are you sure you want to delete this permit?')) {{
                    return;
                }}
                fetch('/api/delete-permit', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ id: permitId }})
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        document.getElementById(`permit-${{permitId}}`).remove();
                    }} else {{
                        alert('Failed to delete permit: ' + data.error);
                    }}
                }});
            }}
        </script>
    </body>
    </html>
    """
 

def get_permit_view_template(permit):
    """Returns the HTML for the public permit view page."""
    # Create a dictionary from the tuple for easier access
    fields = [
        'id', 'businessName', 'businessId', 'addressPoBox', 'phone', 'subcounty', 
        'ward', 'market', 'plotNo', 'activity', 'amount', 'amountInWords', 
        'issueDate', 'expiryDate', 'status'
    ]
    permit_dict = dict(zip(fields, permit))

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Permit Verification</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100">
        <div class="w-full h-full bg-white p-6">
            <div class="mb-6">
                <h1 class="text-3xl font-bold text-gray-800">COUNTY GOVERNMENT OF MURANG'A</h1>
                <h2 class="text-2xl font-semibold text-gray-700 mt-2">Liquor Permit Verification</h2>
            </div>
            <div class="space-y-3 text-gray-700">
                <p><span class="font-semibold">Business Name/ Owner:</span> {permit_dict['businessName']}</p>
                <p><span class="font-semibold">Business ID No:</span> {permit_dict['businessId']}</p>
                <p><span class="font-semibold">Address P.O. Box:</span> {permit_dict['addressPoBox']}</p>
                <p><span class="font-semibold">Phone No.:</span> {permit_dict['phone']}</p>
                <p><span class="font-semibold">Subcounty:</span> {permit_dict['subcounty']}</p>
                <p><span class="font-semibold">Ward:</span> {permit_dict['ward']}</p>
                <p><span class="font-semibold">Market:</span> {permit_dict['market']}</p>
                <p><span class="font-semibold">Plot No:</span> {permit_dict['plotNo']}</p>
                <p><span class="font-semibold">Activity/Business/Profession or Occupation of:</span> {permit_dict['activity']}</p>
                <p><span class="font-semibold">Permit Amount Paid:</span> {permit_dict['amount']}</p>
                <p><span class="font-semibold">Kshs in words:</span> {permit_dict['amountInWords']}</p>
                <p><span class="font-semibold">Date of issue:</span> {permit_dict['issueDate']}</p>
                <p><span class="font-semibold">Expiry Date:</span> {permit_dict['expiryDate']}</p>
                <p class="mt-4 text-green-600 font-bold text-lg"><span class="font-semibold">Status:</span> {permit_dict['status']}</p>
            </div>
        </div>
    </body>
    </html>
    """

# --- HTTP REQUEST HANDLER ---

class PermitServer(http.server.BaseHTTPRequestHandler):
    def _send_response(self, content, content_type="text/html", status=200, headers=None):
        self.send_response(status)
        self.send_header('Content-type', content_type)
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        if isinstance(content, str):
            self.wfile.write(content.encode('utf-8'))
        else:
            self.wfile.write(content)

    def _redirect(self, location='/'):
        self.send_response(303)
        self.send_header('Location', location)
        self.end_headers()

    def is_authenticated(self):
        cookie_header = self.headers.get('Cookie')
        if not cookie_header: return False
        cookie = SimpleCookie()
        cookie.load(cookie_header)
        return cookie.get("session") and cookie["session"].value == SECRET_KEY
     def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)

        # --- Healthcheck endpoint ---
        if path == '/health' or path == '/healthz':
            health = {
                "status": "ok",
                "db": "connected" if self._check_db() else "error"
            }
            self._send_response(json.dumps(health), content_type="application/json")
            return

    def _check_db(self):
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.execute("SELECT 1")
            conn.close()
            return True
        except Exception:
            return False
    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)
        
        if path.startswith('/permit/'):
            permit_id = path.split('/')[-1]
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM permits WHERE id=?", (permit_id,))
            permit = cursor.fetchone()
            conn.close()
            if permit: self._send_response(get_permit_view_template(permit))
            else: self._send_response("Permit not found", status=404)
            return

        if path == '/api/qrcode':
            url_to_encode = query_params.get('url', [''])[0]
            if url_to_encode:
                img = qrcode.make(url_to_encode)
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                img_str = base64.b64encode(buf.getvalue()).decode('utf-8')
                self._send_response(json.dumps({'qr_code_image': f'data:image/png;base64,{img_str}'}), content_type="application/json")
            else:
                self._send_response(json.dumps({'error': 'URL parameter is missing'}), content_type="application/json", status=400)
            return

        if path.startswith('/api/download-qrcode/'):
            permit_id = path.split('/')[-1]
            proto = self.headers.get('X-Forwarded-Proto', 'http')
            host = self.headers.get('Host', f"{self.server.server_address[0]}:{self.server.server_address[1]}")
            url_to_encode = f"{proto}://{host}/permit/{permit_id}"
            
            # Use QRCode class to add a border (padding)
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=1, # Setting border to 1 for a thin padding
            )
            qr.add_data(url_to_encode)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buf = io.BytesIO()
            img.save(buf, format='PNG')
            headers = {'Content-Disposition': f'attachment; filename="qrcode-{permit_id}.png"'}
            self._send_response(buf.getvalue(), content_type="image/png", headers=headers)
            return

        if not self.is_authenticated():
            if path == '/login': self._send_response(get_login_page_template())
            else: self._redirect('/login')
            return
        
        if path == '/logout':
            self.send_response(303)
            self.send_header('Location', '/login')
            self.send_header('Set-Cookie', 'session=; Path=/; HttpOnly; Max-Age=0')
            self.end_headers()
            return

        if path == '/':
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM permits ORDER BY rowid DESC")
            permits = cursor.fetchall()
            conn.close()
            permits_html = ""
            
            proto = self.headers.get('X-Forwarded-Proto', 'http')
            host = self.headers.get('Host', f"{self.server.server_address[0]}:{self.server.server_address[1]}")
            base_url = f"{proto}://{host}"

            if not permits:
                permits_html = "<p>No permits created yet.</p>"
            else:
                for permit in permits:
                    permit_id, business_name = permit[0], permit[1]
                    permit_url = f"{base_url}/permit/{permit_id}"
                    download_url = f"/api/download-qrcode/{permit_id}"
                    permits_html += f"""
                    <div id="permit-{permit_id}" class="border p-4 rounded-lg bg-gray-50 flex flex-col md:flex-row justify-between md:items-center space-y-2 md:space-y-0">
                        <div class="text-center md:text-left">
                            <p class="font-bold">{business_name}</p>
                            <p class="text-sm text-gray-600">ID: {permit_id}</p>
                        </div>
                        <div class="flex flex-wrap justify-center gap-2">
                            <a href="{permit_url}" target="_blank" class="bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600 text-sm">View</a>
                            <button onclick="showQrCode('{permit_id}', '{permit_url}')" class="bg-gray-200 px-3 py-1 rounded hover:bg-gray-300 text-sm">Show QR</button>
                            <a href="{download_url}" class="bg-green-500 text-white px-3 py-1 rounded hover:bg-green-600 text-sm">Download</a>
                            <button onclick="deletePermit('{permit_id}')" class="bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600 text-sm">Delete</button>
                        </div>
                    </div>
                    """
            self._send_response(get_main_page_template(permits_html))
        else:
            self._send_response("Not Found", status=404)

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        if self.path == '/login':
            params = parse_qs(post_data)
            username = params.get('username', [''])[0]
            password = params.get('password', [''])[0]
            if username == USERNAME and check_password_hash(PASSWORD_HASH, password):
                self.send_response(303)
                self.send_header('Location', '/')
                self.send_header('Set-Cookie', f'session={SECRET_KEY}; Path=/; HttpOnly')
                self.end_headers()
            else:
                # Redirect to the external site on failure
                self._redirect('https://eservices.muranga.go.ke')
            return

        if not self.is_authenticated():
            self._send_response("Unauthorized", status=401)
            return

        if self.path == '/':
            params = parse_qs(post_data)
            new_id = uuid.uuid4().hex[:12]
            # Updated to include all new form fields in correct order
            permit_data = (
                new_id,
                params.get('businessName', [''])[0],
                params.get('businessId', [''])[0],
                params.get('addressPoBox', [''])[0],
                params.get('phone', [''])[0],
                params.get('subcounty', [''])[0],
                params.get('ward', [''])[0],
                params.get('market', [''])[0],
                params.get('plotNo', [''])[0],
                params.get('activity', [''])[0],
                params.get('amount', [''])[0],
                params.get('amountInWords', [''])[0],
                params.get('issueDate', [''])[0],
                params.get('expiryDate', [''])[0],
                params.get('status', [''])[0]
            )
            
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", permit_data)
            conn.commit()
            conn.close()
            self._redirect('/')
        
        elif self.path == '/api/delete-permit':
            data = json.loads(post_data)
            permit_id = data.get('id')
            if permit_id:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM permits WHERE id=?", (permit_id,))
                conn.commit()
                conn.close()
                self._send_response(json.dumps({'success': True}), content_type="application/json")
            else:
                self._send_response(json.dumps({'success': False, 'error': 'ID is missing'}), content_type="application/json", status=400)
        else:
            self._send_response("Not Found", status=404)


# --- MAIN EXECUTION ---

if __name__ == "__main__":
    PORT = 7000
    # Before running, make sure to install the required packages:
    # pip install qrcode[pil] werkzeug
    init_db()
    
    Handler = PermitServer
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving at http://localhost:{PORT}")
        print("Login with username 'admin' and password 'Admin@2030$'")
        httpd.serve_forever()
