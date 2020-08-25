import shutil
import subprocess
import sys

import nox

sys.path.insert(0, "")
from src.helpers import (
    BUILD_PATH,
    PUBLIC_PATH,
    RENDER_INFO_FILE,
    IsolatedEnvironment,
    generate_sphinx_config_for,
    load_themes,
)


def _prepare_output_directory(destination, *, delete=True):
    # Clean up existing stuff
    if destination.exists():
        if delete:
            shutil.rmtree(destination)
        else:
            return

    # Make the barebones skeleton
    destination.mkdir()
    (destination / "preview-images").mkdir()
    (destination / "sample-sites").mkdir()


def _generate_docs(session, theme):
    session.log(f" {theme.name} ".center(80, "-"))

    # Setup the isolated environment
    env = IsolatedEnvironment(theme.name)
    session.run("virtualenv", str(env.path), silent=True)

    # Install required packages
    packages = sorted({"sphinx", theme.pypi})  # prevents duplication
    env.install(*packages)

    build_location = BUILD_PATH / "sample-sites" / theme.name
    destination = PUBLIC_PATH / "sample-sites" / theme.name
    if build_location.exists():
        shutil.rmtree(build_location)
    build_location.mkdir(parents=True)

    # Run sphinx
    generate_sphinx_config_for(theme, at=build_location)
    env.run(
        "sphinx-build",
        "-v",
        "-b=html",
        f"-c={build_location}",
        "sample-docs",
        str(build_location),
        silent=True,
    )

    shutil.move(str(build_location), str(destination))


def with_every_theme(session, function, message):
    """Nice little helper, to make looping through all the themes easier.
    """
    themes = load_themes(*session.posargs)
    failed = []
    for theme in themes:
        try:
            function(session, theme)
        except subprocess.CalledProcessError:
            failed.append(theme)
            continue

    if failed:
        parts = [f"Failed to {message.lower()} for:"]
        for theme in failed:
            parts.append(f"- {theme.name}")
        session.error("\n".join(parts))


@nox.session(python=False)
def publish(session):
    session.notify("render-sample-sites")
    session.notify("generate-previews")
    session.notify("render-index")


@nox.session(name="render-sample-sites", python=False)
def render_sample_sites(session):
    _prepare_output_directory(PUBLIC_PATH)
    _prepare_output_directory(BUILD_PATH, delete=False)

    with_every_theme(session, _generate_docs, "Render")


@nox.session(name="generate-previews")
def generate_previews(session):
    assert PUBLIC_PATH.exists(), "Did you run 'render-sample-sites' yet?"

    session.install("selenium", "pillow", "colorama")
    session.run("python", "tools/generate-previews.py", *session.posargs)

    source = BUILD_PATH / "preview-images"
    destination = PUBLIC_PATH / "preview-images"
    for file in source.iterdir():
        assert file.is_file(), repr(file)
        shutil.copy(str(file), str(destination / file.name))


@nox.session(name="render-index")
def render_index(session):
    session.install("jinja2")
    session.run("python", "tools/render-index.py")
    shutil.copy(str(BUILD_PATH / "index.html"), str(PUBLIC_PATH / "index.html"))


@nox.session
def lint(session):
    session.install("pre-commit")
    session.run("pre-commit", "run", "--all-files")
