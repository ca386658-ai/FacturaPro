from flask import Flask, render_template, request, redirect, url_for, flash, session, render_template_string
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from decimal import Decimal
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

# Compatibilidad con URLs que entregue el servicio de nube
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

@app.route(
    "/productos/agregar",
    methods=["POST"]
)
def agregar_producto():

    try:

        codigo = request.form.get(
            "codigo",
            ""
        ).strip()

        nombre = request.form.get(
            "nombre",
            ""
        ).strip()

        categoria = request.form.get(
            "categoria",
            ""
        ).strip()

        precio = Decimal(
            request.form.get(
                "precio",
                "0"
            )
        )

        stock = int(
            request.form.get(
                "stock",
                "0"
            )
        )

        itbis = Decimal(
            request.form.get(
                "itbis",
                "18"
            )
        )

        if not codigo or not nombre:

            flash(
                "El código y el nombre son obligatorios.",
                "error"
            )

            return redirect(
                url_for("productos")
            )

        if precio < 0:

            flash(
                "El precio no puede ser negativo.",
                "error"
            )

            return redirect(
                url_for("productos")
            )

        if stock < 0:

            flash(
                "El stock no puede ser negativo.",
                "error"
            )

            return redirect(
                url_for("productos")
            )

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

                return redirect(
                    url_for("productos")
                )

            flash(
                "Ya existe un producto con ese código.",
                "error"
            )

            return redirect(
                url_for("productos")
            )

        producto = Producto(
            codigo=codigo,
            nombre=nombre,
            categoria=categoria,
            precio=precio,
            stock=stock,
            itbis=itbis,
            activo=True
        )

        db.session.add(
            producto
        )

        db.session.commit()

        flash(
            "Producto agregado correctamente.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print(
            "ERROR AL AGREGAR PRODUCTO:",
            error
        )

        flash(
            "No se pudo agregar el producto.",
            "error"
        )

    return redirect(
        url_for("productos")
    )


# ============================================================
# ELIMINAR PRODUCTO
# ============================================================

@app.route(
    "/productos/eliminar/<int:id>",
    methods=["POST"]
)
def eliminar_producto(id):

    producto = db.session.get(
        Producto,
        id
    )

    if not producto:

        flash(
            "El producto no existe.",
            "error"
        )

        return redirect(
            url_for("productos")
        )

    try:

        producto.activo = False

        db.session.commit()

        flash(
            "Producto eliminado correctamente.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print(
            "ERROR AL ELIMINAR PRODUCTO:",
            error
        )

        flash(
            "No se pudo eliminar el producto.",
            "error"
        )

    return redirect(
        url_for("productos")
    )


# ============================================================
# CLIENTES
# ============================================================

@app.route("/clientes")
def clientes():

    busqueda = request.args.get(
        "buscar",
        ""
    ).strip()

    if busqueda:

        clientes_lista = Cliente.query.filter(
            Cliente.nombre.ilike(
                f"%{busqueda}%"
            )
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

@app.route(
    "/clientes/agregar",
    methods=["POST"]
)
def agregar_cliente():

    try:

        nombre = request.form.get(
            "nombre",
            ""
        ).strip()

        telefono = request.form.get(
            "telefono",
            ""
        ).strip()

        correo = request.form.get(
            "correo",
            ""
        ).strip()

        direccion = request.form.get(
            "direccion",
            ""
        ).strip()

        if not nombre:

            flash(
                "El nombre del cliente es obligatorio.",
                "error"
            )

            return redirect(
                url_for("clientes")
            )

        cliente = Cliente(
            nombre=nombre,
            telefono=telefono,
            correo=correo,
            direccion=direccion
        )

        db.session.add(
            cliente
        )

        db.session.commit()

        flash(
            "Cliente agregado correctamente.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print(
            "ERROR AL AGREGAR CLIENTE:",
            error
        )

        flash(
            "No se pudo agregar el cliente.",
            "error"
        )

    return redirect(
        url_for("clientes")
    )


# ============================================================
# ELIMINAR CLIENTE
# ============================================================

@app.route(
    "/clientes/eliminar/<int:id>",
    methods=["POST"]
)
def eliminar_cliente(id):

    cliente = db.session.get(
        Cliente,
        id
    )

    if not cliente:

        flash(
            "El cliente no existe.",
            "error"
        )

        return redirect(
            url_for("clientes")
        )

    try:

        if cliente.facturas:

            flash(
                "Este cliente tiene facturas asociadas y no puede eliminarse.",
                "error"
            )

            return redirect(
                url_for("clientes")
            )

        db.session.delete(
            cliente
        )

        db.session.commit()

        flash(
            "Cliente eliminado correctamente.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print(
            "ERROR AL ELIMINAR CLIENTE:",
            error
        )

        flash(
            "No se pudo eliminar el cliente.",
            "error"
        )

    return redirect(
        url_for("clientes")
    )


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

@app.route(
    "/factura/guardar",
    methods=["POST"]
)
def guardar_factura():

    try:

        cliente_id = request.form.get(
            "cliente_id"
        )

        items_json = request.form.get(
            "items",
            "[]"
        )

        items = json.loads(
            items_json
        )

        if not items:

            flash(
                "La factura no tiene productos.",
                "error"
            )

            return redirect(
                url_for("nueva_factura")
            )

        subtotal_general = Decimal("0.00")

        itbis_general = Decimal("0.00")

        total_general = Decimal("0.00")

        detalles = []

        for item in items:

            producto_id = int(
                item["producto_id"]
            )

            cantidad = int(
                item["cantidad"]
            )

            if cantidad <= 0:

                raise ValueError(
                    "La cantidad debe ser mayor que cero."
                )

            producto = db.session.get(
                Producto,
                producto_id
            )

            if not producto:

                raise ValueError(
                    "Producto no encontrado."
                )

            if not producto.activo:

                raise ValueError(
                    f"El producto {producto.nombre} está inactivo."
                )

            if producto.stock < cantidad:

                raise ValueError(
                    f"No hay suficiente stock de {producto.nombre}."
                )

            precio = Decimal(
                producto.precio
            )

            tasa_itbis = Decimal(
                producto.itbis or 18
            ) / Decimal("100")

            subtotal_linea = (
                precio *
                cantidad
            )

            itbis_linea = (
                subtotal_linea *
                tasa_itbis
            )

            total_linea = (
                subtotal_linea +
                itbis_linea
            )

            subtotal_general += (
                subtotal_linea
            )

            itbis_general += (
                itbis_linea
            )

            total_general += (
                total_linea
            )

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

        if ultima_factura:

            numero_siguiente = (
                ultima_factura.id + 1
            )

        else:

            numero_siguiente = 1

        numero = (
            f"FAC-{numero_siguiente:06d}"
        )

        factura = Factura(

            numero=numero,

            cliente_id=(
                int(cliente_id)
                if cliente_id
                else None
            ),

            subtotal=subtotal_general,

            itbis=itbis_general,

            total=total_general
        )

        db.session.add(
            factura
        )

        db.session.flush()

        for detalle in detalles:

            producto = detalle["producto"]

            producto.stock -= (
                detalle["cantidad"]
            )

            nuevo_detalle = DetalleFactura(

                factura_id=factura.id,

                producto_id=producto.id,

                cantidad=detalle["cantidad"],

                precio_unitario=detalle["precio"],

                subtotal=detalle["subtotal"],

                itbis=detalle["itbis"],

                total=detalle["total"]
            )

            db.session.add(
                nuevo_detalle
            )

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

        print(
            "ERROR AL GUARDAR FACTURA:",
            error
        )

        flash(
            f"No se pudo guardar la factura: {error}",
            "error"
        )

        return redirect(
            url_for("nueva_factura")
        )


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
# VER FACTURA
# ============================================================

@app.route(
    "/factura/ver/<int:id>"
)
def ver_factura(id):

    factura = db.session.get(
        Factura,
        id
    )

    if not factura:

        flash(
            "La factura no existe.",
            "error"
        )

        return redirect(
            url_for("facturas")
        )

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
            db.func.sum(
                Factura.total
            ),
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

    return render_template(
        "configuracion.html"
    )


# ============================================================
# CREAR TABLAS SI NO EXISTEN
# ============================================================

with app.app_context():

    db.create_all()


# ============================================================
# EJECUTAR SISTEMA
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
