# 🚀 Guía de Despliegue - PostgreSQL con Docker

Esta guía te llevará paso a paso para desplegar la base de datos PostgreSQL en tu servidor Ubuntu vía SSH.

## Esquema de Base de Datos

La base de datos contiene 3 tablas principales:
- **clients** - Clientes de Pika Snacks
- **orders** - Pedidos realizados
- **order_items** - Items individuales de cada pedido

## Requisitos Previos

- Servidor Ubuntu con acceso SSH
- Usuario con permisos sudo
- Conexión a internet en el servidor

---

## Paso 1: Conectar al Servidor

```bash
ssh usuario@ip_servidor
```

Reemplaza `usuario` con tu nombre de usuario y `ip_servidor` con la IP de tu servidor.

---

## Paso 2: Instalar Docker en Ubuntu

```bash
# Actualizar paquetes
sudo apt update && sudo apt upgrade -y

# Instalar dependencias
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# Agregar clave GPG de Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Agregar repositorio de Docker
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Verificar instalación
docker --version
docker compose version

# Agregar tu usuario al grupo docker (para no usar sudo)
sudo usermod -aG docker $USER

# IMPORTANTE: Cerrar sesión y volver a entrar para aplicar cambios
exit
```

Vuelve a conectarte:
```bash
ssh usuario@ip_servidor
```

---

## Paso 3: Crear Directorio del Proyecto

```bash
# En el servidor
mkdir -p ~/pika_db/db
mkdir -p ~/pika_db/data/exports/tables
cd ~/pika_db
```

---

## Paso 4: Subir Archivos desde tu Mac

Abre una **nueva terminal en tu Mac** (no en el servidor):

```bash
# Desde tu Mac local, en el directorio del proyecto
cd /Users/andrescajamarca/Documents/Pika_backend

# Subir archivos de configuración
scp docker-compose.yml usuario@ip_servidor:~/pika_db/
scp db/init.sql usuario@ip_servidor:~/pika_db/db/

# Subir datos para migración (directorio tables con los JSON)
scp -r data/exports/tables usuario@ip_servidor:~/pika_db/data/exports/

# Subir script de migración
scp scripts/migrate_to_postgres.py usuario@ip_servidor:~/pika_db/
```

---

## Paso 5: Configurar Variables de Entorno (Opcional pero Recomendado)

En el servidor, crea un archivo `.env` para personalizar credenciales:

```bash
cd ~/pika_db

cat > .env << 'EOF'
POSTGRES_USER=pika_user
POSTGRES_PASSWORD=TuPasswordSeguro123!
POSTGRES_DB=pika_db
EOF

# Proteger el archivo
chmod 600 .env
```

⚠️ **IMPORTANTE**: Cambia `TuPasswordSeguro123!` por una contraseña segura.

---

## Paso 6: Levantar PostgreSQL

```bash
cd ~/pika_db

# Levantar el contenedor
docker compose up -d

# Verificar que está corriendo
docker compose ps

# Ver logs (opcional)
docker compose logs -f db
```

Deberías ver algo como:
```
NAME      STATUS    PORTS
pika_db   Up        0.0.0.0:5432->5432/tcp
```

---

## Paso 7: Verificar la Base de Datos

```bash
# Conectar a PostgreSQL dentro del contenedor
docker exec -it pika_db psql -U pika_user -d pika_db

# Dentro de psql, verificar tablas:
\dt

# Salir de psql
\q
```

---

## Paso 8: Migrar Datos

```bash
cd ~/pika_db

# Instalar dependencias de Python
sudo apt install -y python3-pip
pip3 install psycopg2-binary

# Ejecutar migración
python3 migrate_to_postgres.py
```

---

## Comandos Útiles

### Gestión del Contenedor

```bash
# Ver estado
docker compose ps

# Detener
docker compose stop

# Iniciar
docker compose start

# Reiniciar
docker compose restart

# Ver logs
docker compose logs -f db

# Detener y eliminar contenedor (mantiene datos)
docker compose down

# Detener y eliminar TODO (incluidos datos)
docker compose down -v
```

### Backup de la Base de Datos

```bash
# Crear backup
docker exec pika_db pg_dump -U pika_user pika_db > backup_$(date +%Y%m%d).sql

# Restaurar backup
cat backup_20241214.sql | docker exec -i pika_db psql -U pika_user -d pika_db
```

### Conectar desde tu Mac Local

Si necesitas conectarte desde tu Mac a la base de datos del servidor:

```bash
# Crear túnel SSH
ssh -L 5432:localhost:5432 usuario@ip_servidor

# En otra terminal, conectar con psql o cualquier cliente
psql -h localhost -U pika_user -d pika_db
```

---

## Estructura Final en el Servidor

```
~/pika_db/
├── docker-compose.yml
├── .env                    # Variables de entorno (credenciales)
├── db/
│   └── init.sql           # Esquema de la base de datos
├── data/
│   └── exports/
│       └── tables/        # Datos JSON para migración
│           ├── clients.json
│           ├── orders.json
│           └── order_items.json
└── migrate_to_postgres.py # Script de migración
```

---

## Solución de Problemas

### Error: "permission denied"
```bash
sudo usermod -aG docker $USER
# Luego cerrar sesión y volver a entrar
```

### Error: "port 5432 already in use"
```bash
# Ver qué está usando el puerto
sudo lsof -i :5432

# Cambiar puerto en docker-compose.yml a otro (ej: 5433:5432)
```

### Error de conexión en migración
```bash
# Verificar que el contenedor está corriendo
docker compose ps

# Verificar logs
docker compose logs db
```

---

## Próximos Pasos (Producción)

Cuando estés listo para producción:

1. **Obtener IP pública** o configurar un dominio
2. **Configurar firewall** (UFW):
   ```bash
   sudo ufw allow 22/tcp    # SSH
   sudo ufw allow 5432/tcp  # PostgreSQL (solo si necesitas acceso externo)
   sudo ufw enable
   ```
3. **Configurar SSL** para conexiones seguras
4. **Configurar backups automáticos** con cron
5. **Monitoreo** con herramientas como pgAdmin o Grafana

---

## Contacto

Si tienes problemas, revisa los logs:
```bash
docker compose logs -f
```
