import os
import re

import psycopg2

from flask import Flask, request, jsonify

from flask_cors import CORS

from dotenv import load_dotenv


load_dotenv()


app = Flask(__name__)


CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "https://rms.monster",
                "https://www.rms.monster"
            ]
        }
    }
)


DATABASE_URL = os.environ.get("DATABASE_URL")


def get_db_connection():

    if not DATABASE_URL:
        raise Exception("DATABASE_URL is not configured")

    return psycopg2.connect(DATABASE_URL)


def validate_email(email):

    pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"

    return re.match(pattern, email) is not None


def validate_phone(phone):

    pattern = r"^\+?[0-9]{7,15}$"

    return re.match(pattern, phone) is not None


@app.route("/")
def home():

    return jsonify({
        "success": True,
        "message": "RMS Monster API is running"
    })


@app.route("/api/health")
def health():

    try:

        connection = get_db_connection()

        cursor = connection.cursor()

        cursor.execute("SELECT 1")

        result = cursor.fetchone()

        cursor.close()

        connection.close()

        return jsonify({
            "success": True,
            "message": "API and database are connected"
        })

    except Exception as error:

        print("Database error:", error)

        return jsonify({
            "success": False,
            "message": "Database connection failed"
        }), 500


@app.route("/api/contact", methods=["POST"])
def create_contact():

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "message": "Request body is required"
            }), 400


        name = str(data.get("name", "")).strip()

        email = str(data.get("email", "")).strip()

        phone = str(data.get("phone", "")).strip()

        company = str(data.get("company", "")).strip()

        project_type = str(
            data.get("project_type", "")
        ).strip()

        message = str(
            data.get("message", "")
        ).strip()


        # -------------------------
        # Required fields
        # -------------------------

        if not name:

            return jsonify({
                "success": False,
                "field": "name",
                "message": "Name is required"
            }), 400


        if not email:

            return jsonify({
                "success": False,
                "field": "email",
                "message": "Email is required"
            }), 400


        if not phone:

            return jsonify({
                "success": False,
                "field": "phone",
                "message": "Phone number is required"
            }), 400


        if not project_type:

            return jsonify({
                "success": False,
                "field": "project_type",
                "message": "Project type is required"
            }), 400


        if not message:

            return jsonify({
                "success": False,
                "field": "message",
                "message": "Message is required"
            }), 400


        # -------------------------
        # Length validation
        # -------------------------

        if len(name) > 100:

            return jsonify({
                "success": False,
                "field": "name",
                "message": "Name cannot exceed 100 characters"
            }), 400


        if len(email) > 150:

            return jsonify({
                "success": False,
                "field": "email",
                "message": "Email cannot exceed 150 characters"
            }), 400


        if len(phone) > 20:

            return jsonify({
                "success": False,
                "field": "phone",
                "message": "Phone number cannot exceed 20 characters"
            }), 400


        if len(company) > 150:

            return jsonify({
                "success": False,
                "field": "company",
                "message": "Company name cannot exceed 150 characters"
            }), 400


        if len(message) > 2000:

            return jsonify({
                "success": False,
                "field": "message",
                "message": "Message cannot exceed 2000 characters"
            }), 400


        # -------------------------
        # Format validation
        # -------------------------

        if not validate_email(email):

            return jsonify({
                "success": False,
                "field": "email",
                "message": "Please enter a valid email address"
            }), 400


        if not validate_phone(phone):

            return jsonify({
                "success": False,
                "field": "phone",
                "message": "Please enter a valid phone number"
            }), 400


        # -------------------------
        # Insert into database
        # -------------------------

        connection = get_db_connection()

        cursor = connection.cursor()


        query = """
            INSERT INTO contacts
            (
                name,
                email,
                phone,
                company,
                project_type,
                message
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
        """


        cursor.execute(
            query,
            (
                name,
                email,
                phone,
                company,
                project_type,
                message
            )
        )


        result = cursor.fetchone()


        connection.commit()


        cursor.close()

        connection.close()


        return jsonify({
            "success": True,
            "message": "Your enquiry has been submitted successfully",
            "contact_id": result[0],
            "created_at": result[1].isoformat()
        }), 201


    except Exception as error:

        print("API error:", error)

        return jsonify({
            "success": False,
            "message": "Unable to submit your enquiry"
        }), 500


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )