from flask import (
    Flask,
    render_template,
    render_template_string,
    request,
    redirect,
    url_for,
    flash,
    session
)
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlsplit
import json
import os

app = Flask(__name__)

# ============================================================
# CONFIGURACIÓN SEGURA
# ============================================================

app.secret_key = os.getenv(
    "SECRET_KEY",
    "facturapro_clave_2026"
)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ============================================================
# INICIO DE SESIÓN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if session.get("logged_in"):
        return redirect(url_for("inicio"))

    destino = request.args.get("next", "/")

    if request.method == "POST":

        password = request.form.get("password", "")
        app_password = os.getenv("APP_PASSWORD", "")

        destino = request.form.get("next", "/")

        # Evitar redirecciones a páginas externas.
        if (
            not destino.startswith("/")
            or destino.startswith("//")
            or "\\" in destino
        ):
            destino = "/"

        if not app_password:
            flash(
                "Falta configurar APP_PASSWORD en Render.",
                "error"
            )

        elif password == app_password:
            session.clear()
            session["logged_in"] = True

            return redirect(destino)

        else:
            flash(
                "Contraseña incorrecta. Inténtalo de nuevo.",
                "error"
            )

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">

        <title>Acceso | FacturaPro</title>

        <style>
            * {
                box-sizing: border-box;
            }

            body {
                margin: 0;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
                background: #10141d;
                color: #ffffff;
                font-family: Arial, sans-serif;
            }

            .login-box {
                width: 100%;
                max-width: 390px;
                padding: 35px;
                background: #1b2230;
                border: 1px solid #30394b;
                border-radius: 16px;
                box-shadow: 0 15px 45px rgba(0,0,0,0.3);
            }

            .logo {
                text-align: center;
                font-size: 32px;
                font-weight: bold;
                margin-bottom: 10px;
            }

            .logo span {
                color: #ef4444;
            }

            .subtitle {
                color: #aab4c5;
                text-align: center;
                margin-bottom: 30px;
            }

            label {
                display: block;
                margin-bottom: 9px;
                font-size: 14px;
            }

            input {
                width: 100%;
                padding: 13px;
                border: 1px solid #3b465b;
                border-radius: 8px;
                background: #10141d;
                color: white;
                outline: none;
                font-size: 16px;
                margin-bottom: 20px;
            }

            input:focus {
                border-color: #3b82f6;
            }

            button {
                width: 100%;
                padding: 14px;
                border: none;
                border-radius: 8px;
                background: #2563eb;
                color: white;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
            }

            button:hover {
                background: #1d4ed8;
            }

            .mensaje {
                padding: 12px;
                margin-bottom: 18px;
                border-radius: 8px;
                background: #49232a;
                color: #fecaca;
                font-size: 14px;
            }

            .pie {
                margin-top: 25px;
                color: #8490a4;
                text-align: center;
                font-size: 12px;
            }
        </style>
    </head>

    <body>
        <div class="login-box">

            <div class="logo">
                Factura<span>Pro</span>
            </div>

            <p class="subtitle">
                Ingresa tu contraseña para continuar
            </p>

            {% for categoria, mensaje in
                get_flashed_messages(with_categories=true) %}
                <div class="mensaje">
                    {{ mensaje }}
                </div>
            {% endfor %}

            <form method="POST" action="{{ url_for('login') }}">

                <input
                    type="hidden"
                    name="next"
                    value="{{ destino }}"
                >

                <label for="password">Contraseña de acceso</label>

                <input
                    type="password"
                    id="password"
                    name="password"
                    placeholder="Escribe tu contraseña"
                    required
                    autofocus
                >

                <button type="submit">
                    Entrar a FacturaPro
                </button>

            </form>

            <div class="pie">
                FacturaPro · Sistema de facturación
            </div>

        </div>
    </body>
    </html>
    """, destino=destino)


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


@app.before_request
def proteger_facturapro():

    # Estas páginas deben funcionar sin iniciar sesión.
    if request.endpoint in ("login", "static"):
        return None

    # Todo lo demás requiere iniciar sesión.
    if not session.get("logged_in"):
        return redirect(
            url_for("login", next=request.path)
        )


# ============================================================
# CONFIGURACIÓN DE POSTGRESQL
# ============================================================

database_url = os.getenv("DATABASE_URL")

if not database_url:
    database_url = (
        "postgresql+psycopg://postgres:"
        + os.getenv("DATABASE_PASSWORD", "")
        + "@localhost:5432/facturapro"
    )

# Compatibilidad con URLs de servicios de nube.
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql+psycopg://",
        1
    )

elif database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ============================================================
# MODELO CLIENTE
# ============================================================

class Cliente(db.Model):

    __tablename__ = "clientes"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nombre = db.Column(
        db.String(100),
        nullable=False
    )

    telefono = db.Column(
        db.String(30)
    )

    correo = db.Column(
        db.String(120)
    )

    direccion = db.Column(
        db.String(200)
    )


# ============================================================
# MODELO PRODUCTO
# ============================================================

class Producto(db.Model):

    __tablename__ = "productos"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    codigo = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    nombre = db.Column(
        db.String(100),
        nullable=False
    )

    categoria = db.Column(
        db.String(100)
    )

    precio = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    stock = db.Column(
        db.Integer,
        default=0
    )

    itbis = db.Column(
        db.Numeric(5, 2),
        default=18.00
    )

    activo = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )


# ============================================================
# MODELO FACTURA
# ============================================================

class Factura(db.Model):

    __tablename__ = "facturas"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    numero = db.Column(
        db.String(30),
        unique=True,
        nullable=False
    )

    fecha = db.Column(
        db.DateTime,
        default=datetime.now,
        nullable=False
    )

    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id")
    )

    subtotal = db.Column(
        db.Numeric(10, 2),
        default=0
    )

    itbis = db.Column(
        db.Numeric(10, 2),
        default=0
    )

    total = db.Column(
        db.Numeric(10, 2),
        default=0
    )

    cliente = db.relationship(
        "Cliente",
        backref="facturas"
    )

    detalles = db.relationship(
        "DetalleFactura",
        backref="factura",
        cascade="all, delete-orphan"
    )


# ============================================================
# MODELO DETALLE DE FACTURA
# ============================================================

class DetalleFactura(db.Model):

    __tablename__ = "detalle_factura"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    factura_id = db.Column(
        db.Integer,
        db.ForeignKey("facturas.id"),
        nullable=False
    )

    producto_id = db.Column(
        db.Integer,
        db.ForeignKey("productos.id"),
        nullable=False
    )

    cantidad = db.Column(
        db.Integer,
        nullable=False
    )

    precio_unitario = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    subtotal = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    itbis = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    total = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    producto = db.relationship(
        "Producto"
    )


# ============================================================
# INICIO
# ============================================================

@app.route("/")
def inicio():

    total_productos = Producto.query.filter_by(
        activo=True
    ).count()

    total_clientes = Cliente.query.count()

    total_facturas = Factura.query.count()

    return render_template(
        "index.html",
        total_productos=total_productos,
        total_clientes=total_clientes,
        total_facturas=total_facturas
    )


# ============================================================
# PRODUCTOS
# ============================================================

@app.route("/productos")
def productos():

    productos = Producto.query.filter_by(
        activo=True
    ).order_by(
        Producto.id.desc()
    ).all()

    return render_template(
        "productos.html",
        productos=productos
    )


# ============================================================
# AGREGAR PRODUCTO
# ============================================================

@app.route("/productos/agregar", methods=["POST"])
def agregar_producto():

    try:

        codigo = request.form.get("codigo", "").strip()
        nombre = request.form.get("nombre", "").strip()
        categoria = request.form.get("categoria", "").strip()

        precio = Decimal(
            request.form.get("precio", "0")
        )

        stock = int(
            request.form.get("stock", "0")
        )

        itbis = Decimal(
            request.form.get("itbis", "18")
        )

        if not codigo or not nombre:
            flash(
                "El código y el nombre son obligatorios.",
                "error"
            )
            return redirect(url_for("productos"))

        if precio < 0:
            flash(
                "El precio no puede ser negativo.",
                "error"
            )
            return redirect(url_for("productos"))

        if stock < 0:
            flash(
                "El stock no puede ser negativo.",
                "error"
            )
            return redirect(url_for("productos"))

        if itbis < 0 or itbis > 100:
            flash(
                "El ITBIS debe estar entre 0 y 100.",
                "error"
            )
            return redirect(url_for("productos"))

        producto_existente = Producto.query.filter_by(
            codigo=codigo
        ).first()

        if producto_existente:

            if not producto_existente.activo:

                producto_existente.nombre = nombre
                producto_existente.categoria = categoria
                producto_existente.precio = precio
                producto_existente.stock = stock
                producto_existente.itbis = itbis
                producto_existente.activo = True

                db.session.commit()

                flash(
                    "El producto fue reactivado correctamente.",
                    "success"
                )

                return redirect(url_for("productos"))

            flash(
                "Ya existe un producto con ese código.",
                "error"
            )
            return redirect(url_for("productos"))

        producto = Producto(
            codigo=codigo,
            nombre=nombre,
            categoria=categoria,
            precio=precio,
            stock=stock,
            itbis=itbis,
            activo=True
        )

        db.session.add(producto)
        db.session.commit()

        flash(
            "Producto agregado correctamente.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print("ERROR AL AGREGAR PRODUCTO:", error)

        flash(
            "No se pudo agregar el producto.",
            "error"
        )

    return redirect(url_for("productos"))


# ============================================================
# ELIMINAR PRODUCTO
# ============================================================

@app.route("/productos/eliminar/<int:id>", methods=["POST"])
def eliminar_producto(id):

    producto = db.session.get(Producto, id)

    if not producto:
        flash(
            "El producto no existe.",
            "error"
        )
        return redirect(url_for("productos"))

    try:

        producto.activo = False
        db.session.commit()

        flash(
            "Producto eliminado correctamente.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print("ERROR AL ELIMINAR PRODUCTO:", error)

        flash(
            "No se pudo eliminar el producto.",
            "error"
        )

    return redirect(url_for("productos"))


# ============================================================
# CLIENTES
# ============================================================

@app.route("/clientes")
def clientes():

    busqueda = request.args.get("buscar", "").strip()

    if busqueda:

        clientes_lista = Cliente.query.filter(
            Cliente.nombre.ilike(f"%{busqueda}%")
        ).order_by(
            Cliente.id.desc()
        ).all()

    else:

        clientes_lista = Cliente.query.order_by(
            Cliente.id.desc()
        ).all()

    return render_template(
        "clientes.html",
        clientes=clientes_lista,
        buscar=busqueda
    )


# ============================================================
# AGREGAR CLIENTE
# ============================================================

@app.route("/clientes/agregar", methods=["POST"])
def agregar_cliente():

    try:

        nombre = request.form.get("nombre", "").strip()
        telefono = request.form.get("telefono", "").strip()
        correo = request.form.get("correo", "").strip()
        direccion = request.form.get("direccion", "").strip()

        if not nombre:
            flash(
                "El nombre del cliente es obligatorio.",
                "error"
            )
            return redirect(url_for("clientes"))

        cliente = Cliente(
            nombre=nombre,
            telefono=telefono,
            correo=correo,
            direccion=direccion
        )

        db.session.add(cliente)
        db.session.commit()

        flash(
            "Cliente agregado correctamente.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print("ERROR AL AGREGAR CLIENTE:", error)

        flash(
            "No se pudo agregar el cliente.",
            "error"
        )

    return redirect(url_for("clientes"))


# ============================================================
# ELIMINAR CLIENTE
# ============================================================

@app.route("/clientes/eliminar/<int:id>", methods=["POST"])
def eliminar_cliente(id):

    cliente = db.session.get(Cliente, id)

    if not cliente:
        flash(
            "El cliente no existe.",
            "error"
        )
        return redirect(url_for("clientes"))

    try:

        if cliente.facturas:
            flash(
                "Este cliente tiene facturas asociadas y no puede eliminarse.",
                "error"
            )
            return redirect(url_for("clientes"))

        db.session.delete(cliente)
        db.session.commit()

        flash(
            "Cliente eliminado correctamente.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print("ERROR AL ELIMINAR CLIENTE:", error)

        flash(
            "No se pudo eliminar el cliente.",
            "error"
        )

    return redirect(url_for("clientes"))


# ============================================================
# NUEVA FACTURA
# ============================================================

@app.route("/factura/nueva")
def nueva_factura():

    clientes_lista = Cliente.query.order_by(
        Cliente.nombre.asc()
    ).all()

    productos_lista = Producto.query.filter_by(
        activo=True
    ).filter(
        Producto.stock > 0
    ).order_by(
        Producto.nombre.asc()
    ).all()

    return render_template(
        "factura_nueva.html",
        clientes=clientes_lista,
        productos=productos_lista
    )


# ============================================================
# GUARDAR FACTURA
# ============================================================

@app.route("/factura/guardar", methods=["POST"])
def guardar_factura():

    try:

        cliente_id = request.form.get("cliente_id")

        items_json = request.form.get("items", "[]")
        items = json.loads(items_json)

        if not items:
            flash(
                "La factura no tiene productos.",
                "error"
            )
            return redirect(url_for("nueva_factura"))

        subtotal_general = Decimal("0.00")
        itbis_general = Decimal("0.00")
        total_general = Decimal("0.00")

        detalles = []

        for item in items:

            producto_id = int(item["producto_id"])
            cantidad = int(item["cantidad"])

            if cantidad <= 0:
                raise ValueError(
                    "La cantidad debe ser mayor que cero."
                )

            producto = db.session.get(
                Producto,
                producto_id
            )

            if not producto:
                raise ValueError("Producto no encontrado.")

            if not producto.activo:
                raise ValueError(
                    f"El producto {producto.nombre} está inactivo."
                )

            if producto.stock < cantidad:
                raise ValueError(
                    f"No hay suficiente stock de {producto.nombre}."
                )

            precio = Decimal(str(producto.precio))

            tasa_itbis = (
                Decimal(str(producto.itbis or 18))
                / Decimal("100")
            )

            subtotal_linea = precio * cantidad
            itbis_linea = subtotal_linea * tasa_itbis
            total_linea = subtotal_linea + itbis_linea

            subtotal_general += subtotal_linea
            itbis_general += itbis_linea
            total_general += total_linea

            detalles.append({
                "producto": producto,
                "cantidad": cantidad,
                "precio": precio,
                "subtotal": subtotal_linea,
                "itbis": itbis_linea,
                "total": total_linea
            })

        ultima_factura = Factura.query.order_by(
            Factura.id.desc()
        ).first()

        numero_siguiente = (
            ultima_factura.id + 1
            if ultima_factura
            else 1
        )

        numero = f"FAC-{numero_siguiente:06d}"

        factura = Factura(
            numero=numero,
            cliente_id=int(cliente_id) if cliente_id else None,
            subtotal=subtotal_general,
            itbis=itbis_general,
            total=total_general
        )

        db.session.add(factura)
        db.session.flush()

        for detalle in detalles:

            producto = detalle["producto"]
            producto.stock -= detalle["cantidad"]

            nuevo_detalle = DetalleFactura(
                factura_id=factura.id,
                producto_id=producto.id,
                cantidad=detalle["cantidad"],
                precio_unitario=detalle["precio"],
                subtotal=detalle["subtotal"],
                itbis=detalle["itbis"],
                total=detalle["total"]
            )

            db.session.add(nuevo_detalle)

        db.session.commit()

        flash(
            "Factura creada correctamente.",
            "success"
        )

        return redirect(
            url_for(
                "ver_factura",
                id=factura.id,
                imprimir=1
            )
        )

    except Exception as error:

        db.session.rollback()

        print("ERROR AL GUARDAR FACTURA:", error)

        flash(
            f"No se pudo guardar la factura: {error}",
            "error"
        )

        return redirect(url_for("nueva_factura"))


# ============================================================
# LISTA DE FACTURAS
# ============================================================

@app.route("/facturas")
def facturas():

    facturas_lista = Factura.query.order_by(
        Factura.id.desc()
    ).all()

    return render_template(
        "facturas.html",
        facturas=facturas_lista
    )


# ============================================================
# ELIMINAR FACTURA
# ============================================================

@app.route("/factura/eliminar/<int:id>", methods=["POST"])
def eliminar_factura(id):
    """Elimina una factura y sus detalles, devolviendo sus cantidades al stock."""

    factura = db.session.get(Factura, id)

    if not factura:
        flash("La factura no existe.", "error")
        return redirect(url_for("facturas"))

    try:
        numero_factura = factura.numero

        # Restaurar al inventario las cantidades vendidas en esta factura.
        for detalle in factura.detalles:
            producto = detalle.producto
            if producto is not None:
                producto.stock = (producto.stock or 0) + detalle.cantidad

        # La relación DetalleFactura usa cascade="all, delete-orphan".
        # Al borrar la factura, SQLAlchemy elimina también sus detalles.
        db.session.delete(factura)
        db.session.commit()

        flash(
            f"La factura {numero_factura} fue eliminada correctamente y el inventario fue actualizado.",
            "success"
        )

    except Exception:
        db.session.rollback()
        app.logger.exception("Error al eliminar factura")
        flash(
            "No se pudo eliminar la factura. No se guardaron cambios.",
            "error"
        )

    return redirect(url_for("facturas"))


# ============================================================
# VER FACTURA
# ============================================================

@app.route("/factura/ver/<int:id>")
def ver_factura(id):

    factura = db.session.get(Factura, id)

    if not factura:
        flash(
            "La factura no existe.",
            "error"
        )
        return redirect(url_for("facturas"))

    return render_template(
        "factura_ver.html",
        factura=factura
    )


# ============================================================
# REPORTES
# ============================================================

@app.route("/reportes")
def reportes():

    total_productos = Producto.query.filter_by(
        activo=True
    ).count()

    total_clientes = Cliente.query.count()
    total_facturas = Factura.query.count()

    ingresos = db.session.query(
        db.func.coalesce(
            db.func.sum(Factura.total),
            0
        )
    ).scalar()

    return render_template(
        "reportes.html",
        total_productos=total_productos,
        total_clientes=total_clientes,
        total_facturas=total_facturas,
        ingresos=ingresos
    )


# ============================================================
# CONFIGURACIÓN
# ============================================================

@app.route("/configuracion")
def configuracion():

    return render_template("configuracion.html")


# ============================================================
# CREAR TABLAS SI NO EXISTEN
# ============================================================

with app.app_context():
    db.create_all()


# ============================================================
# EJECUTAR SISTEMA
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)
