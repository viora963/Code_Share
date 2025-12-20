import mysql.connector
from flask import current_app

def get_conn():
    c = current_app.config
    return mysql.connector.connect(
        host=c["DB_HOST"],
        port=c["DB_PORT"],
        user=c["DB_USER"],
        password=c["DB_PASSWORD"],
        database=c["DB_NAME"],
        autocommit=False,
    )

def fetchone(sql, params=()):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        row = cur.fetchone()
        conn.commit()
        return row
    finally:
        conn.close()

def fetchall(sql, params=()):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.commit()
        return rows
    finally:
        conn.close()

def execute(sql, params=()):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        last_id = cur.lastrowid
        conn.commit()
        return last_id
    except:
        conn.rollback()
        raise
    finally:
        conn.close()
