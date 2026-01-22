# ------------------------------------------------------------
# sfdump Documentation Configuration (Full Enhanced Version)
# ------------------------------------------------------------
import glob
import os
import sys
from importlib.metadata import version as pkg_version

# Make project root importable
sys.path.insert(0, os.path.abspath(".."))

# ------------------------------------------------------------
# Project Information
# ------------------------------------------------------------
project = "sfdump"
author = "Kevin Steptoe"
# Clean version: strip everything after "+"
raw_version = pkg_version("sfdump")
release = raw_version.split("+")[0]  # Used by Sphinx (PDF title, metadata)
version = release  # Short version
# ------------------------------------------------------------
# General Sphinx Extensions
# ------------------------------------------------------------
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.mathjax",
]

# Enable MyST markdown extensions
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "linkify",
]

# ------------------------------------------------------------
# Paths & Patterns
# ------------------------------------------------------------
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "internal_reports/**",
    "_generated/**",
]

# ------------------------------------------------------------
# HTML Theme Configuration (Furo)
# ------------------------------------------------------------
html_theme = "furo"

# Auto-detect logo from src/logos/*
logo_candidates = glob.glob(os.path.join("..", "src", "logos", "*"))
html_logo = logo_candidates[0] if logo_candidates else None

# ------------------------------------------------------------
# HTML Output Options
# ------------------------------------------------------------
html_title = "sfdump Documentation"
html_static_path = ["_static"]

# ------------------------------------------------------------
# PDF / LaTeX Output Enhancements
# ------------------------------------------------------------
latex_engine = "xelatex"

latex_elements = {
    "papersize": "a4paper",
    "pointsize": "11pt",
    "preamble": r"""
\usepackage{fontspec}
\setmainfont{Times New Roman}

\usepackage{geometry}
\geometry{
    a4paper,
    left=25mm,
    right=25mm,
    top=20mm,
    bottom=20mm,
}

% Fix fancyhdr headheight warning
\setlength{\headheight}{14pt}

\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\rhead{\thepage}
\lhead{SF Dump Documentation}

\usepackage{titlesec}
\titleformat{\chapter}[display]
  {\bfseries\Huge}
  {\filleft\Large\thechapter}
  {2ex}
  {\titlerule[1.5pt]\vspace{2ex}\filright}

\titleformat{\section}
  {\Large\bfseries}
  {\thesection}{1em}{}

\usepackage{graphicx}
\usepackage{float}

% Watermark disabled for public release
% \usepackage{draftwatermark}
% \SetWatermarkText{CONFIDENTIAL}
% \SetWatermarkScale{0.25}
% \SetWatermarkColor[gray]{0.92}
% \SetWatermarkAngle{45}

% Reduce excessive page breaks
\usepackage{etoolbox}

% Chapter titles normally cause a page break: remove it
\patchcmd{\chapter}{\cleardoublepage}{}{}{}

% Remove forced page breaks before chapters
\patchcmd{\chapter}{\clearpage}{}{}{}

% Do NOT insert blank page between chapters (book/report behaviour)
\let\cleardoublepage\clearpage

\usepackage{titlesec}
\titlespacing*{\chapter}{0pt}{-10pt}{20pt}
\titlespacing*{\section}{0pt}{5pt}{5pt}
\titlespacing*{\subsection}{0pt}{3pt}{3pt}



\makeatletter
\newcommand{\repoLogo}{"""
    + (html_logo or "")
    + r"""}

\def\maketitle{
  \begin{titlepage}
    \centering
    {\Huge\bfseries\sffamily sfdump Documentation\par}
    \vspace{0.5cm}

    {\Large\itshape Salesforce Offboarding Extraction Manual\par}
    \vspace{1.5cm}

    \ifx\repoLogo\empty
    \else
      \includegraphics[width=0.45\textwidth]{\repoLogo}
      \vspace{1.5cm}
    \fi

    {\Large\bfseries Author:\par}
    {\Large \@author\par}
    \vspace{0.8cm}

    {\large\bfseries Version:\ }{\large\@release\par}
    \vspace{0.5cm}

    {\large \@date \par}
    \vfill

    {\large Generated using Sphinx + Furo Theme\par}
  \end{titlepage}
}
\makeatother
""",
}


# Add logo to PDF build
if html_logo:
    latex_logo = html_logo

# ------------------------------------------------------------
# Required for LaTeX PDF generation (Sphinx)
# ------------------------------------------------------------
latex_documents = [
    (
        "index",  # root document
        "sfdump.tex",  # output .tex filename
        "sfdump Documentation",  # title
        author,  # author
        "manual",  # documentclass
    )
]

# ------------------------------------------------------------
# End of Configuration
# ------------------------------------------------------------
