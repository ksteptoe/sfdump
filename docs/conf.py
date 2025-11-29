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
release = pkg_version("sfdump")  # full version
version_short = release.split("+")[0]  # short version

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
    # Use A4 paper size
    "papersize": "a4paper",
    # Readable default font size
    "pointsize": "11pt",
    "output_mode": "pdf",
    # --------------------------------------------------------
    # Enhanced Title Page + Watermark + Styles
    # --------------------------------------------------------
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

% --------------------------------------------------------
% Watermark (Option 1 – smaller & lighter)
% --------------------------------------------------------
\usepackage{draftwatermark}
\SetWatermarkText{CONFIDENTIAL — EXAMPLE CORP}
\SetWatermarkScale{0.25}        % Much smaller – fits page
\SetWatermarkColor[gray]{0.92}  % Lighter – subtle effect
\SetWatermarkAngle{45}          % Gentle diagonal

% --------------------------------------------------------
% Custom Title Page (Logo, Title, Subtitle, Version, Author)
% --------------------------------------------------------
\makeatletter
\def\maketitle{
  \begin{titlepage}
    \centering

    % =============================
    % Main Title
    % =============================
    {\Huge\bfseries\sffamily sfdump Documentation\par}
    \vspace{0.5cm}

    % =============================
    % Subtitle (edit as desired)
    % =============================
    {\Large\itshape Salesforce Offboarding Extraction Manual\par}
    \vspace{1.5cm}

    % =============================
    % Logo (if provided)
    % =============================
    \ifdefined\logo
      \includegraphics[width=0.45\textwidth]{"""
    + (html_logo or "")
    + r"""}
      \vspace{1.5cm}
    \fi

    % =============================
    % Author
    % =============================
    {\Large\bfseries Author:\par}
    {\Large \@author\par}
    \vspace{0.8cm}

    % =============================
    % Version (auto inserted)
    % =============================
    {\large\bfseries Version:\ }{\large\@release\par}
    \vspace{0.5cm}

    % =============================
    % Date
    % =============================
    {\large \@date \par}
    \vfill

    % =============================
    % Footer Note
    % =============================
    {\large Generated using Sphinx + Furo Theme\par}
  \end{titlepage}
}
\makeatother
""",
}

# Add logo to the title page (if exists)
if html_logo:
    latex_logo = html_logo

# ------------------------------------------------------------
# End of Configuration
# ------------------------------------------------------------
