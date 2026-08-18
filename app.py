from datetime import datetime
from decimal import Decimal

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)

app.config["SECRET_KEY"] = "chave-local-mini-erp"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///erp.db"

db = SQLAlchemy(app)


class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telefone = db.Column(db.String(20), nullable=False)


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)


class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(200))
    preco = db.Column(db.Numeric(10, 2), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)


class MovimentacaoEstoque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(10), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    data = db.Column(db.DateTime, default=datetime.now)
    produto_id = db.Column(
        db.Integer,
        db.ForeignKey("produto.id"),
        nullable=False
    )

    produto = db.relationship("Produto")

class Venda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.now)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("cliente.id"),
        nullable=False
    )

    cliente = db.relationship("Cliente")
    itens = db.relationship(
        "ItemVenda",
        backref="venda",
        cascade="all, delete-orphan"
    )


class ItemVenda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quantidade = db.Column(db.Integer, nullable=False)
    preco_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    venda_id = db.Column(
        db.Integer,
        db.ForeignKey("venda.id"),
        nullable=False
    )
    produto_id = db.Column(
        db.Integer,
        db.ForeignKey("produto.id"),
        nullable=False
    )

    produto = db.relationship("Produto")

    


@app.template_filter("moeda")
def formatar_moeda(valor):
    valor_formatado = f"{valor:,.2f}"

    return (
        valor_formatado
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


@app.before_request
def exigir_login():
    rotas_publicas = {"login", "static"}

    if (
        request.endpoint not in rotas_publicas
        and session.get("usuario_id") is None
    ):
        return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("usuario_id"):
        return redirect(url_for("inicio"))

    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and check_password_hash(
            usuario.senha_hash,
            senha
        ):
            session["usuario_id"] = usuario.id
            session["usuario_nome"] = usuario.nome

            flash("Login realizado com sucesso.", "sucesso")

            return redirect(url_for("inicio"))

        flash("E-mail ou senha inválidos.", "erro")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()

    flash("Você saiu do sistema.", "sucesso")

    return redirect(url_for("login"))

    
@app.route("/")
def inicio():
    total_clientes = Cliente.query.count()
    total_produtos = Produto.query.count()
    total_vendas = Venda.query.count()

    unidades_estoque = sum(
        produto.quantidade
        for produto in Produto.query.all()
    )

    faturamento = sum(
        (venda.total for venda in Venda.query.all()),
        Decimal("0.00")
    )

    return render_template(
        "index.html",
        total_clientes=total_clientes,
        total_produtos=total_produtos,
        total_vendas=total_vendas,
        unidades_estoque=unidades_estoque,
        faturamento=faturamento
    )


@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        telefone = request.form["telefone"]

        novo_cliente = Cliente(
            nome=nome,
            email=email,
            telefone=telefone
        )

        db.session.add(novo_cliente)
        db.session.commit()

        return redirect(url_for("clientes"))

    lista_clientes = Cliente.query.order_by(Cliente.id).all()

    return render_template(
        "clientes.html",
        clientes=lista_clientes
    )


@app.route("/produtos", methods=["GET", "POST"])
def produtos():
    if request.method == "POST":
        nome = request.form["nome"]
        descricao = request.form["descricao"]
        preco = Decimal(request.form["preco"])
        quantidade = int(request.form["quantidade"])

        novo_produto = Produto(
            nome=nome,
            descricao=descricao,
            preco=preco,
            quantidade=quantidade
        )

        db.session.add(novo_produto)
        db.session.commit()

        return redirect(url_for("produtos"))

    lista_produtos = Produto.query.order_by(Produto.id).all()

    return render_template(
        "produtos.html",
        produtos=lista_produtos
    )


@app.route("/estoque")
def estoque():
    lista_produtos = Produto.query.order_by(Produto.nome).all()

    total_produtos = len(lista_produtos)
    total_unidades = sum(
        produto.quantidade for produto in lista_produtos
    )
    valor_total = sum(
        produto.preco * produto.quantidade
        for produto in lista_produtos
    )   
    movimentacoes = MovimentacaoEstoque.query.order_by(
        MovimentacaoEstoque.data.desc()
    ).limit(10).all()

    return render_template(
        "estoque.html",
        produtos=lista_produtos,
        total_produtos=total_produtos,
        total_unidades=total_unidades,
        valor_total=valor_total,
        movimentacoes=movimentacoes
    )
@app.route("/estoque/movimentar/<int:id>", methods=["POST"])
def movimentar_estoque(id):
    produto = Produto.query.get_or_404(id)

    tipo = request.form["tipo"]
    quantidade = int(request.form["quantidade"])

    if quantidade <= 0:
        flash("A quantidade deve ser maior que zero.", "erro")
        return redirect(url_for("estoque"))

    if tipo == "entrada":
        produto.quantidade += quantidade

    elif tipo == "saida":
        if quantidade > produto.quantidade:
            flash("Estoque insuficiente para essa saída.", "erro")
            return redirect(url_for("estoque"))

        produto.quantidade -= quantidade

    else:
        flash("Tipo de movimentação inválido.", "erro")
        return redirect(url_for("estoque"))

    movimentacao = MovimentacaoEstoque(
        tipo=tipo,
        quantidade=quantidade,
        produto_id=produto.id
    )

    db.session.add(movimentacao)
    db.session.commit()

    flash("Movimentação registrada com sucesso.", "sucesso")

    return redirect(url_for("estoque"))


@app.route("/vendas", methods=["GET", "POST"])
def vendas():
    if request.method == "POST":
        cliente_id = int(request.form["cliente_id"])
        produto_id = int(request.form["produto_id"])
        quantidade = int(request.form["quantidade"])

        cliente = Cliente.query.get_or_404(cliente_id)
        produto = Produto.query.get_or_404(produto_id)

        if quantidade <= 0:
            flash("A quantidade deve ser maior que zero.", "erro")
            return redirect(url_for("vendas"))

        if quantidade > produto.quantidade:
            flash("Estoque insuficiente para realizar a venda.", "erro")
            return redirect(url_for("vendas"))

        total = produto.preco * quantidade

        nova_venda = Venda(
            total=total,
            cliente_id=cliente.id
        )

        db.session.add(nova_venda)
        db.session.flush()

        item = ItemVenda(
            quantidade=quantidade,
            preco_unitario=produto.preco,
            venda_id=nova_venda.id,
            produto_id=produto.id
        )

        produto.quantidade -= quantidade

        movimentacao = MovimentacaoEstoque(
            tipo="saida",
            quantidade=quantidade,
            produto_id=produto.id
        )

        db.session.add(item)
        db.session.add(movimentacao)
        db.session.commit()

        flash("Venda registrada com sucesso.", "sucesso")

        return redirect(url_for("vendas"))

    lista_clientes = Cliente.query.order_by(Cliente.nome).all()
    lista_produtos = Produto.query.filter(
        Produto.quantidade > 0
    ).order_by(Produto.nome).all()
    lista_vendas = Venda.query.order_by(Venda.data.desc()).all()

    return render_template(
        "vendas.html",
        clientes=lista_clientes,
        produtos=lista_produtos,
        vendas=lista_vendas
    )


@app.route("/financeiro")
def financeiro():
    lista_vendas = Venda.query.order_by(Venda.data.desc()).all()

    quantidade_vendas = len(lista_vendas)

    faturamento = sum(
        (venda.total for venda in lista_vendas),
        Decimal("0.00")
    )

    if quantidade_vendas > 0:
        ticket_medio = faturamento / quantidade_vendas
    else:
        ticket_medio = Decimal("0.00")

    return render_template(
        "financeiro.html",
        vendas=lista_vendas,
        quantidade_vendas=quantidade_vendas,
        faturamento=faturamento,
        ticket_medio=ticket_medio
    )


@app.route("/relatorios")
def relatorios():
    faturamento = db.session.query(
        db.func.coalesce(db.func.sum(Venda.total), 0)
    ).scalar()

    unidades_vendidas = db.session.query(
        db.func.coalesce(db.func.sum(ItemVenda.quantidade), 0)
    ).scalar()

    unidades_estoque = db.session.query(
        db.func.coalesce(db.func.sum(Produto.quantidade), 0)
    ).scalar()

    vendas_por_produto = db.session.query(
        Produto.nome.label("nome"),
        db.func.sum(ItemVenda.quantidade).label("quantidade"),
        db.func.sum(
            ItemVenda.quantidade * ItemVenda.preco_unitario
        ).label("faturamento")
    ).join(
        ItemVenda,
        Produto.id == ItemVenda.produto_id
    ).group_by(
        Produto.id,
        Produto.nome
    ).order_by(
        db.func.sum(ItemVenda.quantidade).desc()
    ).all()

    compras_por_cliente = db.session.query(
        Cliente.nome.label("nome"),
        db.func.count(Venda.id).label("quantidade_vendas"),
        db.func.sum(Venda.total).label("total_comprado")
    ).join(
        Venda,
        Cliente.id == Venda.cliente_id
    ).group_by(
        Cliente.id,
        Cliente.nome
    ).order_by(
        db.func.sum(Venda.total).desc()
    ).all()

    return render_template(
        "relatorios.html",
        faturamento=faturamento,
        unidades_vendidas=unidades_vendidas,
        unidades_estoque=unidades_estoque,
        vendas_por_produto=vendas_por_produto,
        compras_por_cliente=compras_por_cliente
    )


@app.route("/produtos/editar/<int:id>", methods=["GET", "POST"])
def editar_produto(id):
    produto = Produto.query.get_or_404(id)

    if request.method == "POST":
        produto.nome = request.form["nome"]
        produto.descricao = request.form["descricao"]
        produto.preco = Decimal(request.form["preco"])
        produto.quantidade = int(request.form["quantidade"])

        db.session.commit()

        return redirect(url_for("produtos"))

    return render_template(
        "editar_produto.html",
        produto=produto
    )


@app.route("/produtos/excluir/<int:id>", methods=["POST"])
def excluir_produto(id):
    produto = Produto.query.get_or_404(id)

    db.session.delete(produto)
    db.session.commit()

    return redirect(url_for("produtos"))


@app.route("/clientes/editar/<int:id>", methods=["GET", "POST"])
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    if request.method == "POST":
        cliente.nome = request.form["nome"]
        cliente.email = request.form["email"]
        cliente.telefone = request.form["telefone"]

        db.session.commit()

        return redirect(url_for("clientes"))

    return render_template(
        "editar_cliente.html",
        cliente=cliente
    )

@app.route("/clientes/excluir/<int:id>", methods=["POST"])
def excluir_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    db.session.delete(cliente)
    db.session.commit()

    return redirect(url_for("clientes"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        administrador = Usuario.query.filter_by(
            email="admin@minierp.com"
        ).first()

        if administrador is None:
            administrador = Usuario(
                nome="Administrador",
                email="admin@minierp.com",
                senha_hash=generate_password_hash("admin123")
            )

            db.session.add(administrador)
            db.session.commit()

    app.run(debug=True)