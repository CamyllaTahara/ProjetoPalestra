
import mysql.connector
from config import DB_CONFIG

def conectar_bd():
    return mysql.connector.connect(**DB_CONFIG)