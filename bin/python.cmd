@echo off

set parentPath=%~dp0..\
set ROOT_DIR=%parentPath%
pushd %parentPath%

REM Make sure we don't accidentally use Python libraries outside the virtualenv
set PYTHONPATH=
set PYTHONHOME=

call %~dp0activate_conda.cmd

REM Call Python in the virtualenv
python %*

popd