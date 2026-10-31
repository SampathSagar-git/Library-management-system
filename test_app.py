import unittest
from datetime import datetime, timezone
from app import create_app
from models.database import get_db
from models.book import Book
from models.reservation import DeskReservation

class SmartLibraryTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.client = cls.app.test_client()

    def test_01_homepage_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your Smart Library", response.data)
        self.assertIn(b"One Click Away", response.data)

    def test_02_books_catalog(self):
        response = self.client.get('/books')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Books Catalog", response.data)
        self.assertIn(b"Artificial Intelligence", response.data)

    def test_03_login_and_dashboards(self):
        # 1. Student login
        res = self.client.post('/login', data={
            'email': 'alex@student.edu',
            'password': 'Student@123'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Student Dashboard", res.data)
        self.assertIn(b"Alex Turner", res.data)

        # 2. Access student dashboard directly
        res_stu = self.client.get('/student/dashboard')
        self.assertEqual(res_stu.status_code, 200)
        self.assertIn(b"AI &amp; Graph-Powered Book Recommendations", res_stu.data)

        # Logout
        self.client.get('/logout', follow_redirects=True)

        # 3. Staff login
        res_staff = self.client.post('/login', data={
            'email': 'prof.smith@library.edu',
            'password': 'Staff@123'
        }, follow_redirects=True)
        self.assertEqual(res_staff.status_code, 200)
        self.assertIn(b"Faculty &amp; Staff Portal", res_staff.data)
        self.client.get('/logout', follow_redirects=True)

        # 4. Admin login
        res_admin = self.client.post('/login', data={
            'email': 'admin@library.edu',
            'password': 'Admin@123'
        }, follow_redirects=True)
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn(b"Administrator Control Panel", res_admin.data)
        self.assertIn(b"chartLoanTrends", res_admin.data)

    def test_04_desk_booking_and_double_booking_prevention(self):
        # Login as student
        self.client.post('/login', data={'email': 'sarah@student.edu', 'password': 'Student@123'})

        today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        # Check desk availability API
        res_api = self.client.get(f'/api/desks/availability?date={today_str}&start_time=11:00&duration=2')
        self.assertEqual(res_api.status_code, 200)
        json_data = res_api.get_json()
        self.assertIn('desks', json_data)

        # Reserve desk B201 for today 11:00 to 13:00
        res_book = self.client.post('/desks/reserve', data={
            'desk_number': 'B201',
            'zone': 'Collaborative Zone',
            'booking_date': today_str,
            'start_time': '11:00',
            'duration_hours': 2,
            'purpose': 'Group Project'
        }, follow_redirects=True)
        self.assertEqual(res_book.status_code, 200)
        self.assertIn(b"successfully reserved", res_book.data)

        # Double-booking attempt for the exact overlapping slot by another user
        self.client.get('/logout')
        self.client.post('/login', data={'email': 'alex@student.edu', 'password': 'Student@123'})
        res_conflict = self.client.post('/desks/reserve', data={
            'desk_number': 'B201',
            'zone': 'Collaborative Zone',
            'booking_date': today_str,
            'start_time': '12:00', # Overlaps with 11:00 - 13:00!
            'duration_hours': 2,
            'purpose': 'Double booking test'
        }, follow_redirects=True)
        self.assertEqual(res_conflict.status_code, 200)
        # Should be blocked!
        self.assertIn(b"already booked", res_conflict.data)

    def test_05_admin_analytics_api(self):
        self.client.get('/logout')
        self.client.post('/login', data={'email': 'admin@library.edu', 'password': 'Admin@123'})
        res = self.client.get('/admin/api/analytics')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('trends', data)
        self.assertIn('categories', data)
        self.assertIn('desks', data)

    def test_06_loan_and_return_lifecycle(self):
        # 1. Student requests loan for CLRS book
        self.client.get('/logout')
        self.client.post('/login', data={'email': 'michael@student.edu', 'password': 'Student@123'})

        db = get_db()
        book_doc = db.books.find_one({"isbn": "978-0262046305"})
        book_id = str(book_doc['_id'])
        initial_avail = book_doc['available_copies']

        # Request loan
        res_req = self.client.post(f'/loans/request/{book_id}', follow_redirects=True)
        self.assertEqual(res_req.status_code, 200)
        self.assertIn(b"Loan requested", res_req.data)

        # Verify loan in pending status
        loan_doc = db.loans.find_one({"user_email": "michael@student.edu", "book_id": book_id, "status": "pending"})
        self.assertIsNotNone(loan_doc)
        loan_id = str(loan_doc['_id'])

        # 2. Admin logs in and approves loan
        self.client.get('/logout')
        self.client.post('/login', data={'email': 'admin@library.edu', 'password': 'Admin@123'})
        res_app = self.client.post(f'/loans/approve/{loan_id}', follow_redirects=True)
        self.assertEqual(res_app.status_code, 200)
        self.assertIn(b"Loan approved", res_app.data)

        # Check that available copies decreased by 1
        book_after = db.books.find_one({"_id": book_doc['_id']})
        self.assertEqual(book_after['available_copies'], initial_avail - 1)

        # 3. Admin processes return
        res_ret = self.client.post(f'/loans/return/{loan_id}', data={'condition': 'Good'}, follow_redirects=True)
        self.assertEqual(res_ret.status_code, 200)
        self.assertIn(b"Book returned", res_ret.data)

        # Check available copies restored
        book_final = db.books.find_one({"_id": book_doc['_id']})
        self.assertEqual(book_final['available_copies'], initial_avail)

if __name__ == '__main__':
    unittest.main()
