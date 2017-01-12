:: Asset API
::
:: This file is called whenever a user enters an asset, such as Cat or Shot01.
::
:: Arguments:
:: 	 %1: Name of asset, e.g. Fiona
:: 	 %2: Absolute path to asset parent directory, e.g. m:\f01_projects\p999_Demo\assets
::
:: Example:
::   $ p999_Meindbender_Sync
::   $ Fiona

@echo off

set ASSET=%1
set ROOT=%2%ASSET%

If Not Exist %ROOT% (
	mkdir %ROOT%
)

echo+
echo %ASSET% -----------
echo+
echo   Type application and task.
echo+
echo   For example:
echo+
echo   $ maya modeling
echo   $ maya rigging
echo   $ nuke comp
echo+
echo --------------------------------------

pushd %ROOT%
