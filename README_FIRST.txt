EVENT MANAGEMENT SYSTEM - BACKEND STARTER

1. Extract this ZIP into your existing D:\EventManagementSystem folder.
   Merge the app folder if asked. Do not replace your .venv folder.
2. Copy .env.example and rename the copy to .env.
3. Edit .env:
   - Set DB_PASSWORD to the MySQL root password you chose during installation.
   - Replace FLASK_SECRET_KEY with a long random secret.
4. In VS Code terminal, activate your project environment:
   .\.venv\Scripts\Activate.ps1
5. Install dependencies in THIS environment:
   python -m pip install -r requirements.txt
6. Start the application:
   python run.py
7. Open http://127.0.0.1:5000/ in your browser.
8. Test database connectivity at http://127.0.0.1:5000/health
9. Register a customer or organizer at /register.
   Organizer accounts start as PENDING.
10. There is deliberately no public admin registration. We will create the
    first admin account securely in the next step.

IMPORTANT:
- Never share your .env file or MySQL password.
- This is a local development starter, not a production deployment.
- Do not expose the Flask debug server to the public internet.
