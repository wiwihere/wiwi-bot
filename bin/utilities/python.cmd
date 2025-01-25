@echo off

REM Change current path to parent of bin folder
set parentPath=%~dp0..\..\
set ROOT_DIR=%parentPath%
pushd %parentPath%

REM Make sure we don't accidentally use Python libraries outside the virtualenv
set PYTHONPATH=
set PYTHONHOME=

call %~dp0\activate_conda.cmd

REM Call Python in the virtualenv
python %*

popd