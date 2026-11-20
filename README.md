# MyAlert! · Reportes vecinales

Reimplementación independiente de MyAlert! en Python, inspirada en la [versión del bootcamp](https://github.com/AndresSCP/Proyecto). Flask gestiona las rutas y renderiza las vistas con Jinja. MySQL guarda las cuentas y los reportes. El frontend usa HTML, CSS y JavaScript.

La aplicación incluye registro, inicio de sesión, perfiles con historial de reportes, publicación de incidentes, mapa de reportes y un panel para activar o desactivar cuentas de cliente. Se puede escribir el lugar y seleccionar un punto en Leaflet. La aplicación usa teselas de OpenStreetMap en el navegador. La búsqueda de direcciones y el feed externo quedan pendientes.

## Ejecutar localmente en Windows

Necesitas Python 3.10 o posterior y acceso a una instancia de MySQL. En un cliente SQL con permisos administrativos, crea una base vacía y una cuenta local. Sustituye la contraseña de ejemplo por una propia:

    CREATE DATABASE myalert CHARACTER SET utf8mb4;
    CREATE USER 'myalert'@'localhost' IDENTIFIED BY 'CAMBIA_ESTA_CONTRASEÑA';
    GRANT SELECT, INSERT, UPDATE, CREATE, REFERENCES ON myalert.* TO 'myalert'@'localhost';

En PowerShell, desde la carpeta del proyecto:

    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    $env:MYALERT_SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
    $env:MYSQL_PASSWORD = 'TU_CONTRASEÑA_MYSQL'
    .\.venv\Scripts\python.exe -m flask --app app init-db
    .\.venv\Scripts\python.exe -m flask --app app create-admin
    .\.venv\Scripts\python.exe -m flask --app app run

Abre http://127.0.0.1:5000. Puedes crear una cuenta de cliente desde la interfaz o usar la cuenta administrativa creada en la terminal. Conserva la misma clave secreta entre reinicios si quieres conservar las sesiones. Puedes configurar el servidor con MYSQL_HOST, MYSQL_PORT, MYSQL_USER y MYSQL_DATABASE. Usa MYALERT_HTTPS=1 si sirves la aplicación por HTTPS.

El esquema de esta versión es nuevo. Utiliza una base distinta si quieres preservar los datos de la versión Java. El mapa necesita conexión para cargar Leaflet y las teselas. Antes de un despliegue público, revisa la [política de teselas de OpenStreetMap](https://operations.osmfoundation.org/policies/tiles/). Los reportes están visibles para quienes puedan acceder a la aplicación.
