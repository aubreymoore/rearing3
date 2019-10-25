# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

# -------------------------------------------------------------------------
# This is a sample controller
# - index is the default action of any application
# - user is required for authentication and authorization
# - download is for downloading files uploaded in the db (does streaming)
# -------------------------------------------------------------------------

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import subprocess
import pandas as pd
import lifelines
from lifelines import KaplanMeierFitter, statistics
import re

def tex_escape(text):
    """
        :param text: a plain text message
        :return: the message escaped to appear correctly in LaTeX
    """
    conv = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}',
        '<': r'\textless{}',
        '>': r'\textgreater{}',
    }
    regex = re.compile('|'.join(re.escape(unicode(key)) for key in sorted(conv.keys(), key = lambda item: - len(item))))
    return regex.sub(lambda match: conv[match.group()], text)

def caca():
    return dict(rows = db(db.btl).select())

def bioassay_summary():
    sql = """
    SELECT bioassay_name, date_start_bioassay, date_end_bioassay, max(date_observed), julianday(date_end_bioassay)-julianday(date_start_bioassay) AS duration
    FROM btl, obs
    WHERE 
        bioassay_name is not null
        and bioassay_name is not ''
        and btl.id=obs.btl
    GROUP BY bioassay_name
    ORDER BY bioassay_name;
    """
    rows = db.executesql(sql, as_dict=True)
    return locals()

def checkin_form():
    form = SQLFORM.factory(
        Field('date_checkin', 'date', requires=IS_DATE(), label='Checkin date'),
        Field('beetle_count', 'integer', label= 'Number of beetles', requires=IS_INT_IN_RANGE(1, 1000)))
    if form.process().accepted:
        response.flash = 'form accepted'
        date_checkin = form.vars.date_checkin
        beetle_count = form.vars.beetle_count
        result = db.executesql("select min(jar) from btl;")
        minjar = min(0, result[0][0])
        result = db.executesql("select max(id) from btl;")
        firstid = result[0][0] + 1
        for i in range(form.vars.beetle_count):
            minjar = minjar - 1
            sql = "INSERT INTO btl (date_checkin, jar) VALUES ('{}', {});".format(date_checkin, minjar)
            db.executesql(sql)
        result = db.executesql("select max(id) from btl;")
        lastid = result[0][0]
        return dict(beetle_count=beetle_count, firstid=firstid, lastid=lastid)
    elif form.errors:
        response.flash = 'form has errors'
    return dict(form=form)


def fixit():
    sql = "select * from btl limit 10;"
    rows = db.executesql(sql)
    for r in rows:
        print(r)
    return

def download_db():
    return response.stream('applications/rearing/databases/storage.sqlite')

def test_logger():
    logger.debug('message from controller.')
    return

@auth.requires_login()
def import_obs_csv():
    test_logger()
    logger.debug('starting import_obs_csv.')
    if request.vars.csvfile != None:
        # set values
        table = db[request.vars.table]
        file = request.vars.csvfile.file

        # import csv file
        logger.debug('*** {} importing {}'.format(auth.user.email, request.vars.csvfile.filename))
        table.import_from_csv_file(file)

        response.flash = 'Data uploaded'
    return dict()


@auth.requires_login()
def import_btl_csv():
    logger.debug('starting import_btl_csv.')
    if request.vars.csvfile != None:
        logger.debug('message from import_btl_csv.')

        # set values
        table = db[request.vars.table]
        file = request.vars.csvfile.file

        # import csv file
        logger.debug('can you see this?')
        logger.debug('*** {} importing {}'.format(auth.user.email, request.vars.csvfile.filename))
        table.import_from_csv_file(file)
    return dict()

@auth.requires_login()
def clear_log():
    with open('rearing.log', 'w'):
        pass
    return

@auth.requires_login()
def view_log():
    return response.stream('rearing.log')

@auth.requires_login()
def view_tex_log():
    return response.stream('report.log')

@auth.requires_login()
def view_tex():
    return response.stream('report.tex')

def wiki():
    auth.wikimenu() # add the wiki to the menu
    return auth.wiki() 

@auth.requires_login()
def btl_form():
    form = SQLFORM.smartgrid(db.btl)
    return locals()

@auth.requires_login()
def obs_form():
    form = SQLFORM.smartgrid(db.obs)
    return locals()

@auth.requires_login()
def bioassay_form():
    form = SQLFORM.smartgrid(db.bioassay)
    return locals()

def report_form():
    # Generate a sorted list of bioassay_names to be used in a dropdown
    # This list includes names for reps and the bioassays the reps are part of
    sql='select bioassay_name from btl where bioassay_name IS NOT NULL group by bioassay_name;'
    choices = db.executesql(sql)
    choices = [i[0] for i in choices]
    withoutreps = ['{}-%'.format(i.split('-')[0]) for i in choices]
    choices = set(choices).union(set(withoutreps))
    choices = list(choices)
    choices.sort()
    if request.vars.bioassay_name_pattern:
        generate_pdf(request.vars.bioassay_name_pattern)
    return locals()

def plot_mass_by_treatment(bioassay_name_pattern):
    """
    Generates a plot of mass curves for each beetle in a bioassay treatment.
    Plots are saved as PDF files in the current work directory.
    Bioassay name can specify an replicate (example: 'DUG42-1') or all
    replicates within a bioassay (example: 'DUG42').
    """

    # Get data
    sql = """
    SELECT bioassay_treatment,
        julianday(date_observed) - julianday(date_start_bioassay) AS days,
        btl, mass
    FROM btl, obs
    WHERE
        btl.id = obs.btl
    AND
        bioassay_name LIKE '{}';
    """.format(bioassay_name_pattern)
    logger.debug(sql)

    rows = db.executesql(sql, as_dict=True)
    df = pd.DataFrame(rows)
    logger.debug('{} rows returned.'.format(df.shape[0]))

    # Save plots as PDF files
    file_list = []
    for treatment in df.bioassay_treatment.unique():
        fig, ax = plt.subplots(figsize=(18,6))
        for name, group in df[df.bioassay_treatment==treatment].groupby('btl'):
            group.plot(x='days', 
                       y='mass', 
                       xlim = [df.days.min(), df.days.max()],
                       ylim = [df.mass.min(), df.mass.max()],
                       ax=ax, 
                       label=name, 
                       linewidth=5)
        ax.set_xlabel('days after treatment')
        ax.set_ylabel('mass (mg)')
        file_name = 'mass-{}.pdf'.format(treatment.replace(' ', '-'))
        fig.savefig(file_name)
        file_list.append(file_name)
    return file_list


def get_postmortem_images(bioassay_name_pattern):
    """
    """
    # Get data
    sql = """
    SELECT id, bioassay_name, bioassay_treatment, pm_image
    FROM btl
    WHERE bioassay_name LIKE '{}' AND pm_image IS NOT NULL AND pm_image != '';
    """.format(bioassay_name_pattern)
    rows = db.executesql(sql, as_dict=True)
    df = pd.DataFrame(rows)
    df.dropna(inplace=True)
    if df.empty:
        return ''

    # generate tex
    
    tex = ''
    for treatment in df.bioassay_treatment.unique():
        tex += r'\subsection{' + treatment + r'}' + '\n'
        for index, row in df[df.bioassay_treatment==treatment].iterrows():
            tex += r'\begin{figure}[h!]' + '\n'
            tex += r'    \centering' + '\n'
            tex += r'    \includegraphics[width=\linewidth, height=\textheight, keepaspectratio]{applications/rearing/uploads/' + row.pm_image + r'}' + '\n'
            tex += r'    \caption{Bioassay: ' + row.bioassay_name + '; Treatment: ' + row.bioassay_treatment + r'; Beetle ID: ' + str(row.id) + r'}' + '\n'
            tex += r'\end{figure}' + '\n'
            tex += r'\clearpage' + '\n'
    return tex


def generate_pdf(bioassay_name_pattern):
    # Mod by Aubrey Moore 2019-04-17.
    # The following sql was modified to solve a problem.
    # The modified sql does a selects records where the full bioassay name is matcched.
    # Previously, a search for 'PNG' matched [PNG-1, PNG-2, PNG-3, PNGperOS-1, PNGperOS-2, PNGperOS-3]
    # Now, a search for 'PNG' matches only [PNG-1, PNG-2, PNG-3].
    #sql = "SELECT * FROM btl WHERE bioassay_name LIKE '%{}%'".format(bioassay_name)
    
    bioassay_name = bioassay_name_pattern.replace('%','')
    
    sql = "SELECT * FROM btl WHERE bioassay_name LIKE '{}'".format(bioassay_name_pattern)
    rows = db.executesql(sql, as_dict=True)
    df = pd.DataFrame(rows)
    print df.info()
    t, e = lifelines.utils.datetimes_to_durations(
        start_times=pd.to_datetime(df.date_start_bioassay),
        end_times=pd.to_datetime(df.date_died),
        fill_date=pd.to_datetime(df.date_end_bioassay))
    print t
    df['t'] = t
    df['e'] = e

    # Create survorship plot
    fig, ax = plt.subplots(figsize=(18,6))
    kmf = KaplanMeierFitter()
    for name, grouped_df in df.groupby('bioassay_treatment'):
        kmf.fit(grouped_df['t'], grouped_df['e'], label=name)
        kmf.plot(ax=ax, linewidth=5, ci_show=False)
    ax.set_xlabel('days after treatment')
    ax.set_ylabel('proportion dead')
    ax.set_ylim([0,1])
    fig.savefig('survivorshipfig.pdf')
    
    # Create motality-table-tex
    results = statistics.pairwise_logrank_test(df['t'], df['bioassay_treatment'], df['e'])
    s = r'''
        \begin{table}[h!]
        \centering
        \caption{Pairwise differences among mortality curves.}
    '''
    s += results.summary.to_latex()
    s += '\end{table}'
    mortality_table_tex = s
    print s
    
    # Create document
    s = r'''
        \documentclass[11pt]{scrartcl}
        \usepackage{textcomp}
        \usepackage{gensymb}
        \usepackage{graphicx}
        \usepackage{grffile} %required because there are multiple dot characters in my file names
        \usepackage{booktabs}
        \usepackage[letterpaper, margin=1in]{geometry}
        
        \titlehead{\centering\includegraphics[width=0.75in]{applications/rearing/static/images/crb_logo.png}\\
        	University of Guam Coconut Rhinoceros Beetle Biological Control Project\\
        	Bioassay Report generated by CRB Rearing Database v.20190317\\
        	https://aubreymoore.pythonanywhere.com/rearing}
        \title{---title---}
        \author{Aubrey Moore and Jim Grasela\\University of Guam Coconut Rhinoceros Beetle Biocontrol Project}

\begin{document}

    \begin{titlepage}
        \maketitle
		\tableofcontents
	\end{titlepage}

        ---description---
        
        \clearpage
        \section{Mortality}
        \includegraphics[width=\textwidth]{survivorshipfig.pdf}
        ---mortality-table-tex---
        
        \clearpage
        \section{Mass}
        ---mass plots---
        
        \clearpage
        \section{Postmortem Images}
        ---postmortem images---
        
        \end{document}
    '''
    s = s.replace('---title---', tex_escape(bioassay_name))
    s = s.replace('---mortality-table-tex---', mortality_table_tex)
    
    # Replace ---description--- with tex from database
    sql = 'select tex from bioassay where name="{}"'.format(bioassay_name_pattern)
    logger.debug(sql)
    rows = db.executesql(sql)
    if rows:
        logger.debug(rows[0])
        description = rows[0][0]
        description = description.encode('utf8')
        logger.debug('type: {}   description: {}'.format(type(description), description))
        s = s.replace('---description---', description)
    else:
        s = s.replace('---description---', '')
   
    #Replace ---mass plots---
    file_list = plot_mass_by_treatment(bioassay_name_pattern)
    logger.debug('file_list: {}'.format(file_list))
    tex = ''
    for file_name in file_list:
        tex += r'\subsection*{' + file_name.replace('-', ' ') + r'}'
        tex += '\n'
        tex += r'\includegraphics[width=\textwidth]{' + file_name+ r'}'
        tex += '\n'
    s = s.replace('---mass plots---', tex)
    if False:
        #Replace ---postmortem images---
        tex = get_postmortem_images(bioassay_name_pattern)
        s = s.replace('---postmortem images---', tex)
    
    #s = tex_escape(s)
    logger.debug(s)
    
    # Generate PDF
    with open('report.tex', "w") as f:
        f.write(s)
    result = subprocess.call(['pdflatex', 'report.tex'])
    result = subprocess.call(['pdflatex', 'report.tex'])
    return response.stream('report.pdf')


def index():
    return locals()

def user():
    """
    exposes:
    http://..../[app]/default/user/login
    http://..../[app]/default/user/logout
    http://..../[app]/default/user/register
    http://..../[app]/default/user/profile
    http://..../[app]/default/user/retrieve_password
    http://..../[app]/default/user/change_password
    http://..../[app]/default/user/bulk_register
    use @auth.requires_login()
        @auth.requires_membership('group name')
        @auth.requires_permission('read','table name',record_id)
    to decorate functions that need access control
    also notice there is http://..../[app]/appadmin/manage/auth to allow administrator to manage users
    """
    return dict(form=auth())


@cache.action()
def download():
    """
    allows downloading of uploaded files
    http://..../[app]/default/download/[filename]
    """
    return response.download(request, db)


def call():
    """
    exposes services. for example:
    http://..../[app]/default/call/jsonrpc
    decorate with @services.jsonrpc the functions to expose
    supports xml, json, xmlrpc, jsonrpc, amfrpc, rss, csv
    """
    return service()
