
from flask import (
    Flask, render_template, render_template_string,
    request, redirect, url_for, flash, session
)
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import os

app = Flask(__name__)

# ============================================================
# CONFIGURACIÓN
# ============================================================

app.secret_key = os.getenv("SECRET_KEY", "facturapro_clave_2026")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

database_url = os.getenv("DATABASE_URL")

if not database_url:
    database_url = (
        "postgresql+psycopg://postgres:"
        + os.getenv("DATABASE_PASSWORD", "")
        + "@localhost:5432/facturapro"
    )

if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://", "postgresql+psycopg://", 1
    )
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def facturas_validas():
    return Factura.query.filter(
        db.or_(
            Factura.estado.is_(None),
            Factura.estado != "anulada"
        )
    )


def dinero(valor):
    return Decimal(str(valor or 0)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def actualizar_estado_pago(factura):
    total = dinero(factura.total)
    pagado = dinero(factura.monto_pagado)

    if pagado >= total:
        factura.monto_pagado = total
        factura.estado_pago = "pagada"
    elif pagado > 0:
        factura.estado_pago = "parcial"
    else:
        factura.estado_pago = "pendiente"


# ============================================================
# MODELO CLIENTE
# ============================================================

class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(30))
    correo = db.Column(db.String(120))
    direccion = db.Column(db.String(200))
    activo = db.Column(db.Boolean, default=True, nullable=False)


# ============================================================
# MODELO PRODUCTO
# ============================================================

class Producto(db.Model):
    __tablename__ = "productos"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(100))
    costo = db.Column(db.Numeric(10, 2), nullable=True)
    precio = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, default=0)
    itbis = db.Column(db.Numeric(5, 2), default=18.00)
    activo = db.Column(db.Boolean, default=True, nullable=False)

    @property
    def margen_ganancia(self):
        if self.costo is None or self.costo <= 0:
            return None

        return (
            (self.precio - self.costo) / self.costo
        ) * Decimal("100")


# ============================================================
# MODELO FACTURA
# ============================================================

class Factura(db.Model):
    __tablename__ = "facturas"

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(30), unique=True, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.now, nullable=False)

    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id")
    )

    subtotal = db.Column(db.Numeric(10, 2), default=0)
    itbis = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), default=0)

    # Estado administrativo de la factura
    estado = db.Column(
        db.String(20),
        nullable=False,
        default="activa",
        server_default="activa"
    )

    fecha_anulacion = db.Column(db.DateTime, nullable=True)

    # NUEVO: CONTROL DE PAGOS
    estado_pago = db.Column(
        db.String(20),
        nullable=False,
        default="pendiente",
        server_default="pendiente"
    )

    monto_pagado = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0,
        server_default="0"
    )

    cliente = db.relationship("Cliente", backref="facturas")

    detalles = db.relationship(
        "DetalleFactura",
        backref="factura",
        cascade="all, delete-orphan"
    )

    @property
    def saldo_pendiente(self):
        return max(
            dinero(self.total) - dinero(self.monto_pagado),
            Decimal("0.00")
        )


# ============================================================
# MODELO DETALLE DE FACTURA
# ============================================================

class DetalleFactura(db.Model):
    __tablename__ = "detalle_factura"

    id = db.Column(db.Integer, primary_key=True)

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

    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    itbis = db.Column(db.Numeric(10, 2), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)

    producto = db.relationship("Producto")


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

        if (
            not destino.startswith("/")
            or destino.startswith("//")
            or "\\" in destino
        ):
            destino = "/"

        if not app_password:
            flash("Falta configurar APP_PASSWORD en Render.", "error")

        elif password == app_password:
            session.clear()
            session["logged_in"] = True
            return redirect(destino)

        else:
            flash("Contraseña incorrecta.", "error")

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Acceso | FacturaPro</title>
        <style>
            * { box-sizing: border-box; }
            body {
                margin: 0;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
                background: #10141d;
                color: white;
                font-family: Arial, sans-serif;
            }
            .login-box {
                width: 100%;
                max-width: 390px;
                padding: 35px;
                background: #1b2230;
                border: 1px solid #30394b;
                border-radius: 16px;
            }
            .logo {
                text-align: center;
                font-size: 32px;
                font-weight: bold;
                margin-bottom: 10px;
            }
            .logo span { color: #ef4444; }
            .subtitle {
                color: #aab4c5;
                text-align: center;
                margin-bottom: 30px;
            }
            label {
                display: block;
                margin-bottom: 9px;
            }
            input {
                width: 100%;
                padding: 13px;
                border: 1px solid #3b465b;
                border-radius: 8px;
                background: #10141d;
                color: white;
                margin-bottom: 20px;
            }
            button {
                width: 100%;
                padding: 14px;
                border: none;
                border-radius: 8px;
                background: #2563eb;
                color: white;
                font-weight: bold;
                cursor: pointer;
            }
            .mensaje {
                padding: 12px;
                margin-bottom: 18px;
                background: #49232a;
                border-radius: 8px;
            }
        </style>
    </head>
    <body>
        <div class="login-box">
            <div class="logo">Factura<span>Pro</span></div>
            <p class="subtitle">Ingresa tu contraseña para continuar</p>

            {% for categoria, mensaje in get_flashed_messages(with_categories=true) %}
                <div class="mensaje">{{ mensaje }}</div>
            {% endfor %}

            <form method="POST">
                <input type="hidden" name="next" value="{{ destino }}">
                <label>Contraseña de acceso</label>
                <input type="password" name="password"
                       placeholder="Escribe tu contraseña" required>
                <button type="submit">Entrar a FacturaPro</button>
            </form>
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

    if request.endpoint in ("login", "static"):
        return None

    if not session.get("logged_in"):
        return redirect(
            url_for("login", next=request.path)
        )


# ============================================================
# DASHBOARD INTELIGENTE
# ============================================================

@app.route("/")
def inicio():

    try:
        ahora = datetime.now()

        inicio_mes = ahora.replace(
            day=1, hour=0, minute=0,
            second=0, microsecond=0
        )

        activas = facturas_validas()

        total_productos = Producto.query.filter_by(
            activo=True
        ).count()

        total_clientes = Cliente.query.filter_by(
            activo=True
        ).count()

        total_facturas = activas.count()

        ventas_mes = db.session.query(
            db.func.coalesce(db.func.sum(Factura.total), 0)
        ).filter(
            Factura.fecha >= inicio_mes,
            Factura.estado != "anulada"
        ).scalar()

        ventas_totales = db.session.query(
            db.func.coalesce(db.func.sum(Factura.total), 0)
        ).filter(
            Factura.estado != "anulada"
        ).scalar()

        facturas_mes = activas.filter(
            Factura.fecha >= inicio_mes
        ).count()

        # Cobros reales del mes.
        cobros_mes = db.session.query(
            db.func.coalesce(
                db.func.sum(Factura.monto_pagado), 0
            )
        ).filter(
            Factura.fecha >= inicio_mes,
            Factura.estado != "anulada"
        ).scalar()

        # Cuentas pendientes de cobro.
        saldo_pendiente = db.session.query(
            db.func.coalesce(
                db.func.sum(
                    Factura.total - Factura.monto_pagado
                ), 0
            )
        ).filter(
            Factura.estado != "anulada",
            Factura.monto_pagado < Factura.total
        ).scalar()

        facturas_pendientes = activas.filter(
            Factura.monto_pagado == 0
        ).count()

        facturas_parciales = activas.filter(
            Factura.monto_pagado > 0,
            Factura.monto_pagado < Factura.total
        ).count()

        facturas_pagadas = activas.filter(
            Factura.monto_pagado >= Factura.total
        ).count()

        productos_bajo_stock = Producto.query.filter(
            Producto.activo.is_(True),
            Producto.stock <= 5
        ).order_by(
            Producto.stock.asc()
        ).all()

        # Gráfica de ventas de los últimos siete días.
        ventas_labels = []
        ventas_datos = []

        for i in range(6, -1, -1):

            dia = (ahora - timedelta(days=i)).date()

            inicio_dia = datetime.combine(
                dia, datetime.min.time()
            )

            fin_dia = inicio_dia + timedelta(days=1)

            venta_dia = db.session.query(
                db.func.coalesce(
                    db.func.sum(Factura.total), 0
                )
            ).filter(
                Factura.fecha >= inicio_dia,
                Factura.fecha < fin_dia,
                Factura.estado != "anulada"
            ).scalar()

            ventas_labels.append(dia.strftime("%d/%m"))
            ventas_datos.append(float(venta_dia or 0))

        ultimas_facturas = Factura.query.order_by(
            Factura.fecha.desc()
        ).limit(5).all()

        return render_template(
            "index.html",

            total_productos=total_productos,
            total_clientes=total_clientes,
            total_facturas=total_facturas,

            ventas_mes=ventas_mes,
            ventas_totales=ventas_totales,
            facturas_mes=facturas_mes,

            cobros_mes=cobros_mes,
            saldo_pendiente=saldo_pendiente,

            facturas_pendientes=facturas_pendientes,
            facturas_parciales=facturas_parciales,
            facturas_pagadas=facturas_pagadas,

            productos_bajo_stock=productos_bajo_stock,

            ventas_labels=ventas_labels,
            ventas_datos=ventas_datos,
            ventas_labels_json=json.dumps(ventas_labels),
            ventas_datos_json=json.dumps(ventas_datos),

            ultimas_facturas=ultimas_facturas
        )

    except Exception:
        db.session.rollback()
        app.logger.exception("Error en Dashboard Inteligente")
        raise


# ============================================================
# PRODUCTOS
# ============================================================

@app.route("/productos")
def productos():

    lista = Producto.query.filter_by(
        activo=True
    ).order_by(
        Producto.id.desc()
    ).all()

    return render_template(
        "productos.html",
        productos=lista
    )


@app.route("/productos/agregar", methods=["POST"])
def agregar_producto():

    try:
        codigo = request.form.get("codigo", "").strip()
        nombre = request.form.get("nombre", "").strip()
        categoria = request.form.get("categoria", "").strip()

        costo = Decimal(request.form.get("costo", "0"))
        margen = Decimal(request.form.get("margen", "30"))
        stock = int(request.form.get("stock", "0"))
        itbis = Decimal(request.form.get("itbis", "18"))

        if not codigo or not nombre:
            raise ValueError("Código y nombre son obligatorios.")

        if not costo.is_finite() or costo < 0:
            raise ValueError("Costo inválido.")

        if not margen.is_finite() or margen < 0 or margen > 1000:
            raise ValueError("Ganancia inválida.")

        if stock < 0:
            raise ValueError("Stock inválido.")

        if not itbis.is_finite() or itbis < 0 or itbis > 100:
            raise ValueError("ITBIS inválido.")

        precio = (
            costo * (1 + margen / 100)
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        existente = Producto.query.filter_by(
            codigo=codigo
        ).first()

        if existente:

            if existente.activo:
                raise ValueError("Ya existe ese código.")

            existente.nombre = nombre
            existente.categoria = categoria
            existente.costo = costo
            existente.precio = precio
            existente.stock = stock
            existente.itbis = itbis
            existente.activo = True

        else:

            db.session.add(
                Producto(
                    codigo=codigo,
                    nombre=nombre,
                    categoria=categoria,
                    costo=costo,
                    precio=precio,
                    stock=stock,
                    itbis=itbis,
                    activo=True
                )
            )

        db.session.commit()
        flash("Producto guardado correctamente.", "success")

    except (ValueError, InvalidOperation):
        db.session.rollback()
        flash("Revisa los datos del producto.", "error")

    except Exception:
        db.session.rollback()
        app.logger.exception("Error al agregar producto")
        flash("No se pudo guardar el producto.", "error")

    return redirect(url_for("productos"))


@app.route("/productos/eliminar/<int:id>", methods=["POST"])
def eliminar_producto(id):

    producto = db.session.get(Producto, id)

    if not producto:
        flash("Producto no encontrado.", "error")
        return redirect(url_for("productos"))

    try:
        producto.activo = False
        db.session.commit()
        flash("Producto eliminado correctamente.", "success")

    except Exception:
        db.session.rollback()
        flash("No se pudo eliminar el producto.", "error")

    return redirect(url_for("productos"))


# ============================================================
# CLIENTES
# ============================================================

@app.route("/clientes")
def clientes():

    buscar = request.args.get("buscar", "").strip()

    consulta = Cliente.query.filter_by(activo=True)

    if buscar:
        consulta = consulta.filter(
            Cliente.nombre.ilike(f"%{buscar}%")
        )

    lista = consulta.order_by(
        Cliente.id.desc()
    ).all()

    return render_template(
        "clientes.html",
        clientes=lista,
        buscar=buscar
    )


@app.route("/clientes/agregar", methods=["POST"])
def agregar_cliente():

    try:
        nombre = request.form.get("nombre", "").strip()

        if not nombre:
            raise ValueError("El nombre es obligatorio.")

        cliente = Cliente(
            nombre=nombre,
            telefono=request.form.get("telefono", "").strip(),
            correo=request.form.get("correo", "").strip(),
            direccion=request.form.get("direccion", "").strip(),
            activo=True
        )

        db.session.add(cliente)
        db.session.commit()

        flash("Cliente agregado correctamente.", "success")

    except Exception:
        db.session.rollback()
        app.logger.exception("Error al agregar cliente")
        flash("No se pudo agregar el cliente.", "error")

    return redirect(url_for("clientes"))


@app.route("/clientes/eliminar/<int:id>", methods=["POST"])
def eliminar_cliente(id):

    cliente = db.session.get(Cliente, id)

    if not cliente:
        flash("Cliente no encontrado.", "error")
        return redirect(url_for("clientes"))

    try:
        cliente.activo = False
        db.session.commit()

        flash(
            "Cliente retirado. Sus facturas se conservaron.",
            "success"
        )

    except Exception:
        db.session.rollback()
        flash("No se pudo eliminar el cliente.", "error")

    return redirect(url_for("clientes"))


# ============================================================
# NUEVA FACTURA
# ============================================================

@app.route("/factura/nueva")
def nueva_factura():

    clientes_lista = Cliente.query.filter_by(
        activo=True
    ).order_by(
        Cliente.nombre.asc()
    ).all()

    productos_lista = Producto.query.filter(
        Producto.activo.is_(True),
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
        items = json.loads(request.form.get("items", "[]"))

        if not isinstance(items, list) or not items:
            raise ValueError("La factura no tiene productos.")

        cliente = None

        if cliente_id:
            cliente = db.session.get(Cliente, int(cliente_id))

            if not cliente or not cliente.activo:
                raise ValueError("Cliente inválido.")

        cantidades = {}

        for item in items:

            producto_id = int(item["producto_id"])
            cantidad = int(item["cantidad"])

            if cantidad <= 0:
                raise ValueError("Cantidad inválida.")

            cantidades[producto_id] = (
                cantidades.get(producto_id, 0) + cantidad
            )

        productos = {}

        for producto_id, cantidad in cantidades.items():

            producto = db.session.execute(
                db.select(Producto)
                .where(Producto.id == producto_id)
                .with_for_update()
            ).scalar_one_or_none()

            if not producto or not producto.activo:
                raise ValueError("Producto no disponible.")

            if producto.stock < cantidad:
                raise ValueError(
                    f"Stock insuficiente de {producto.nombre}."
                )

            productos[producto_id] = producto

        subtotal_general = Decimal("0.00")
        itbis_general = Decimal("0.00")
        total_general = Decimal("0.00")
        detalles = []

        for producto_id, cantidad in cantidades.items():

            producto = productos[producto_id]

            precio = dinero(producto.precio)

            tasa = (
                Decimal(str(producto.itbis or 18))
                / Decimal("100")
            )

            subtotal = dinero(precio * cantidad)
            itbis = dinero(subtotal * tasa)
            total = subtotal + itbis

            subtotal_general += subtotal
            itbis_general += itbis
            total_general += total

            detalles.append({
                "producto": producto,
                "cantidad": cantidad,
                "precio": precio,
                "subtotal": subtotal,
                "itbis": itbis,
                "total": total
            })

        ultima = Factura.query.order_by(
            Factura.id.desc()
        ).first()

        numero_siguiente = ultima.id + 1 if ultima else 1
        numero = f"FAC-{numero_siguiente:06d}"

        factura = Factura(
            numero=numero,
            cliente_id=int(cliente_id) if cliente_id else None,
            subtotal=dinero(subtotal_general),
            itbis=dinero(itbis_general),
            total=dinero(total_general),
            estado="activa",

            # TODA FACTURA NUEVA COMIENZA PENDIENTE.
            estado_pago="pendiente",
            monto_pagado=Decimal("0.00")
        )

        db.session.add(factura)
        db.session.flush()

        for detalle in detalles:

            producto = detalle["producto"]
            producto.stock -= detalle["cantidad"]

            db.session.add(
                DetalleFactura(
                    factura_id=factura.id,
                    producto_id=producto.id,
                    cantidad=detalle["cantidad"],
                    precio_unitario=detalle["precio"],
                    subtotal=detalle["subtotal"],
                    itbis=detalle["itbis"],
                    total=detalle["total"]
                )
            )

        db.session.commit()

        flash("Factura creada correctamente.", "success")

        return redirect(
            url_for("ver_factura", id=factura.id, imprimir=1)
        )

    except (
        ValueError, TypeError, KeyError,
        json.JSONDecodeError, InvalidOperation
    ) as error:

        db.session.rollback()
        flash(f"No se pudo guardar: {error}", "error")
        return redirect(url_for("nueva_factura"))

    except Exception:

        db.session.rollback()
        app.logger.exception("Error al guardar factura")

        flash("Error al guardar la factura.", "error")
        return redirect(url_for("nueva_factura"))


# ============================================================
# LISTA DE FACTURAS
# ============================================================

@app.route("/facturas")
def facturas():

    lista = Factura.query.order_by(
        Factura.id.desc()
    ).all()

    return render_template(
        "facturas.html",
        facturas=lista
    )


# ============================================================
# REGISTRAR PAGO O ABONO
# ============================================================

@app.route("/factura/pagar/<int:id>", methods=["POST"])
def registrar_pago(id):

    try:
        factura = db.session.execute(
            db.select(Factura)
            .where(Factura.id == id)
            .with_for_update()
        ).scalar_one_or_none()

        if not factura:
            flash("Factura no encontrada.", "error")
            return redirect(url_for("facturas"))

        if factura.estado == "anulada":
            flash("No puedes registrar pagos en una factura anulada.", "error")
            return redirect(url_for("ver_factura", id=id))

        monto_texto = request.form.get("monto", "").strip()

        if not monto_texto:
            raise ValueError("Debes indicar el monto del pago.")

        monto = Decimal(monto_texto)

        if not monto.is_finite() or monto <= 0:
            raise ValueError("El pago debe ser mayor que cero.")

        monto = dinero(monto)

        saldo = factura.saldo_pendiente

        if monto > saldo:
            raise ValueError(
                f"El pago supera el saldo pendiente de RD$ {saldo:.2f}."
            )

        factura.monto_pagado = dinero(
            factura.monto_pagado
        ) + monto

        actualizar_estado_pago(factura)

        db.session.commit()

        if factura.estado_pago == "pagada":
            flash(
                f"Factura {factura.numero} pagada completamente.",
                "success"
            )
        else:
            flash(
                f"Abono registrado. Saldo restante: "
                f"RD$ {factura.saldo_pendiente:.2f}.",
                "success"
            )

    except (ValueError, InvalidOperation) as error:

        db.session.rollback()
        flash(str(error), "error")

    except Exception:

        db.session.rollback()
        app.logger.exception("Error al registrar pago")
        flash("No se pudo registrar el pago.", "error")

    return redirect(url_for("ver_factura", id=id))


# ============================================================
# MARCAR FACTURA COMO PAGADA
# ============================================================

@app.route("/factura/marcar-pagada/<int:id>", methods=["POST"])
def marcar_pagada(id):

    try:
        factura = db.session.execute(
            db.select(Factura)
            .where(Factura.id == id)
            .with_for_update()
        ).scalar_one_or_none()

        if not factura:
            flash("Factura no encontrada.", "error")

        elif factura.estado == "anulada":
            flash("No puedes pagar una factura anulada.", "error")

        else:
            factura.monto_pagado = dinero(factura.total)
            factura.estado_pago = "pagada"

            db.session.commit()

            flash("Factura marcada como pagada.", "success")

    except Exception:
        db.session.rollback()
        app.logger.exception("Error al marcar factura pagada")
        flash("No se pudo actualizar el pago.", "error")

    return redirect(url_for("ver_factura", id=id))


# ============================================================
# ANULAR FACTURA
# ============================================================

@app.route("/factura/anular/<int:id>", methods=["POST"])
def anular_factura(id):

    try:
        factura = db.session.execute(
            db.select(Factura)
            .where(Factura.id == id)
            .with_for_update()
        ).scalar_one_or_none()

        if not factura:
            flash("La factura no existe.", "error")
            return redirect(url_for("facturas"))

        if factura.estado == "anulada":
            flash("La factura ya está anulada.", "error")
            return redirect(url_for("facturas"))

        for detalle in factura.detalles:

            producto = detalle.producto

            if producto:
                producto.stock = (
                    producto.stock or 0
                ) + detalle.cantidad

        factura.estado = "anulada"
        factura.fecha_anulacion = datetime.now()

        db.session.commit()

        flash(
            f"Factura {factura.numero} anulada. "
            "El inventario fue restaurado.",
            "success"
        )

    except Exception:

        db.session.rollback()
        app.logger.exception("Error al anular factura")
        flash("No se pudo anular la factura.", "error")

    return redirect(url_for("facturas"))


# ============================================================
# REACTIVAR FACTURA
# ============================================================

@app.route("/factura/reactivar/<int:id>", methods=["POST"])
def reactivar_factura(id):

    try:
        factura = db.session.execute(
            db.select(Factura)
            .where(Factura.id == id)
            .with_for_update()
        ).scalar_one_or_none()

        if not factura:
            flash("La factura no existe.", "error")
            return redirect(url_for("facturas"))

        if factura.estado != "anulada":
            flash("La factura no está anulada.", "error")
            return redirect(url_for("facturas"))

        cantidades = {}

        for detalle in factura.detalles:

            cantidades[detalle.producto_id] = (
                cantidades.get(detalle.producto_id, 0)
                + detalle.cantidad
            )

        productos = {}

        for producto_id, cantidad in cantidades.items():

            producto = db.session.execute(
                db.select(Producto)
                .where(Producto.id == producto_id)
                .with_for_update()
            ).scalar_one_or_none()

            if not producto:
                raise ValueError(
                    "Falta un producto de esta factura."
                )

            if (producto.stock or 0) < cantidad:
                raise ValueError(
                    f"Inventario insuficiente para {producto.nombre}."
                )

            productos[producto_id] = producto

        for producto_id, cantidad in cantidades.items():
            productos[producto_id].stock -= cantidad

        factura.estado = "activa"
        factura.fecha_anulacion = None

        db.session.commit()

        flash("Factura reactivada correctamente.", "success")

    except ValueError as error:

        db.session.rollback()
        flash(str(error), "error")

    except Exception:

        db.session.rollback()
        app.logger.exception("Error al reactivar factura")
        flash("No se pudo reactivar la factura.", "error")

    return redirect(url_for("facturas"))


# ============================================================
# VER FACTURA
# ============================================================

@app.route("/factura/ver/<int:id>")
def ver_factura(id):

    factura = db.session.get(Factura, id)

    if not factura:
        flash("Factura no encontrada.", "error")
        return redirect(url_for("facturas"))

    return render_template(
        "factura_ver.html",
        factura=factura
    )


# ============================================================
# REPORTE GENERAL
# ============================================================

@app.route("/reportes")
def reportes():

    activas = facturas_validas()

    total_productos = Producto.query.filter_by(
        activo=True
    ).count()

    total_clientes = Cliente.query.filter_by(
        activo=True
    ).count()

    total_facturas = activas.count()

    ingresos = db.session.query(
        db.func.coalesce(
            db.func.sum(Factura.total), 0
        )
    ).filter(
        Factura.estado != "anulada"
    ).scalar()

    cobrado = db.session.query(
        db.func.coalesce(
            db.func.sum(Factura.monto_pagado), 0
        )
    ).filter(
        Factura.estado != "anulada"
    ).scalar()

    pendiente = db.session.query(
        db.func.coalesce(
            db.func.sum(
                Factura.total - Factura.monto_pagado
            ), 0
        )
    ).filter(
        Factura.estado != "anulada",
        Factura.monto_pagado < Factura.total
    ).scalar()

    pagadas = activas.filter(
        Factura.monto_pagado >= Factura.total
    ).count()

    pendientes = activas.filter(
        Factura.monto_pagado == 0
    ).count()

    parciales = activas.filter(
        Factura.monto_pagado > 0,
        Factura.monto_pagado < Factura.total
    ).count()

    return render_template(
        "reportes.html",
        total_productos=total_productos,
        total_clientes=total_clientes,
        total_facturas=total_facturas,
        ingresos=ingresos,
        cobrado=cobrado,
        pendiente=pendiente,
        pagadas=pagadas,
        pendientes=pendientes,
        parciales=parciales
    )


# ============================================================
# CONFIGURACIÓN
# ============================================================

@app.route("/configuracion")
def configuracion():
    return render_template("configuracion.html")


# ============================================================
# MIGRACIÓN SEGURA DE BASE DE DATOS
# ============================================================

with app.app_context():

    db.create_all()

    with db.engine.begin() as conexion:

        conexion.exec_driver_sql("""
            ALTER TABLE clientes
            ADD COLUMN IF NOT EXISTS activo
            BOOLEAN NOT NULL DEFAULT TRUE
        """)

        conexion.exec_driver_sql("""
            ALTER TABLE productos
            ADD COLUMN IF NOT EXISTS costo
            NUMERIC(10, 2) NULL
        """)

        conexion.exec_driver_sql("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS estado
            VARCHAR(20) NOT NULL DEFAULT 'activa'
        """)

        conexion.exec_driver_sql("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS fecha_anulacion
            TIMESTAMP NULL
        """)

        # NUEVAS COLUMNAS PARA CONTROL DE PAGOS

        conexion.exec_driver_sql("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS estado_pago
            VARCHAR(20) NOT NULL DEFAULT 'pendiente'
        """)

        conexion.exec_driver_sql("""
            ALTER TABLE facturas
            ADD COLUMN IF NOT EXISTS monto_pagado
            NUMERIC(10, 2) NOT NULL DEFAULT 0
        """)

        # Normalizar registros antiguos sin modificar
        # sus importes ni marcar pagos que no conocemos.

        conexion.exec_driver_sql("""
            UPDATE facturas
            SET estado_pago = 'pendiente'
            WHERE estado_pago IS NULL
               OR estado_pago NOT IN ('pendiente', 'parcial', 'pagada')
        """)

        conexion.exec_driver_sql("""
            UPDATE facturas
            SET monto_pagado = 0
            WHERE monto_pagado IS NULL
        """)


# ============================================================
# EJECUTAR SISTEMA
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=os.getenv("FLASK_DEBUG", "0") == "1"
    )
