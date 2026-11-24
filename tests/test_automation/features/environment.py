"""
Behave hooks: a fresh Nodeon driver (own temporary folder, own settings) for
every scenario, closed again afterwards - scenarios never influence each other.
"""
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from nodeon_driver import NodeonDriver  # noqa: E402


def before_scenario(context, scenario):
    context.workdir = Path(tempfile.mkdtemp(prefix="nodeon-behave-"))
    context.drv = NodeonDriver(context.workdir)


def after_scenario(context, scenario):
    drv = getattr(context, "drv", None)
    if drv is not None:
        drv.close()
        drv.restore()
    shutil.rmtree(context.workdir, ignore_errors=True)
