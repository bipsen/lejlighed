import os
import numpy as np
import pandas as pd
import io
import time
import seaborn as sns
import math
from flask import Flask, render_template, request, redirect, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils import database_exists
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from scipy import stats
from datetime import datetime

project_dir = os.path.dirname(os.path.abspath(__file__))
database_file = "sqlite:///{}".format(
    os.path.join(project_dir, "offerdatabase.db"))

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = database_file
app.config["SQLALCHEMY_TRACK_MODIFICATION"] = False

db = SQLAlchemy(app)


class Offer(db.Model):
    __tablename__ = 'offers'
    date = db.Column(db.String(80), unique=True,
                     nullable=False, primary_key=True)
    placement = db.Column(db.String(3), unique=True,
                          nullable=False, primary_key=False)


def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


@app.route('/', methods=["GET", "POST"])
def home():

    offers = None

    if request.form:
        try:
            offer = Offer(date=request.form.get("date"),
                          placement=request.form.get("placement"))
            db.session.add(offer)
            db.session.commit()
        except Exception as e:
            print("Failed to add offer")
            print(e)
            db.session.rollback()
    the_date = "No date"
    offers = Offer.query.all()
    if offers:
        df = pd.read_sql(sql=db.session.query(Offer)
                         .with_entities(Offer.date,
                                        Offer.placement).statement,
                         con=db.session.bind)
        df.date = pd.to_datetime(df.date)
        df.date = df['date'].apply(lambda d: time.mktime(d.timetuple()))
        df.placement = pd.to_numeric(df.placement)

        slope, intercept, r_value, p_value, std_err = stats.linregress(
            df['date'], df['placement'])
        if not math.isnan(slope):
            the_date = datetime.fromtimestamp(-intercept/slope).date()

    return render_template("home.html", offers=offers, the_date=the_date)


@app.route("/update", methods=["POST"])
def update():
    try:
        newdate = request.form.get("newdate")
        olddate = request.form.get("olddate")
        offer = Offer.query.filter_by(date=olddate).first()
        offer.date = newdate
        db.session.commit()
    except Exception as e:
        print("Couldn't update offer date")
        print(e)
    return redirect("/")


@app.route("/delete", methods=["POST"])
def delete():
    date = request.form.get("date")
    offer = Offer.query.filter_by(date=date).first()
    db.session.delete(offer)
    db.session.commit()
    return redirect("/")


# Matplotlib stuff
@app.route('/plot.png')
def plot_png():
    fig = create_figure()
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')


def create_figure():
    df = pd.read_sql(sql=db.session.query(Offer)
                     .with_entities(Offer.date,
                                    Offer.placement).statement,
                     con=db.session.bind)
    df.date = pd.to_datetime(df.date)
    # df.date = df['date'].apply(lambda d: time.mktime(d.timetuple()))
    df.placement = pd.to_numeric(df.placement)

    # Ugly regplot date hack from
    # https://stackoverflow.com/questions/44354614/seaborn-regplot-using-datetime64-as-the-x-axis
    df = df.sort_values('date')
    df['date_of_offer'] = pd.factorize(df['date'])[0] + 1
    mapping = dict(zip(df['date_of_offer'], df['date'].dt.date))

    fig = Figure()
    axis = fig.add_subplot(1, 1, 1)

    # CHANGE THIS BACK TO date_of_offer
    sns.regplot('date_of_offer', 'placement', data=df, ax=axis)

    labels = pd.Series(axis.get_xticks()).map(mapping).fillna('')
    axis.set_xticklabels(labels)

    return fig


if __name__ == "__main__":

    app.run()

    if not database_exists(database_file):
       db.create_all()
       db.session.commit()
