@echo off
rem You need https://github.com/Adobe-CEP/CEP-Resources/raw/master/ZXPSignCMD/4.1.1/win64/ZXPSignCmd.exe

rem You need https://partners.adobe.com/exchangeprogram/creativecloud/support/exman-com-line-tool.html

rem !!! make sure you run windows power shell as admin

set pwd="PSext581"

echo ">>> creating certificate ..."
%YOWZA_PIPE_PATH%/utils/ZXPSignCmd -selfSignedCert CZ Prague OrbiTools "Signing robot" %pwd% certificate.p12
echo ">>> building extension"
%YOWZA_PIPE_PATH%/utils/ZXPSignCmd -sign ../extension/ ../extension.zxp certificate.p12 %pwd%
echo ">>> installing extensiom"
%YOWZA_PIPE_PATH%/utils/ExManCmd_Win/ExManCmd.exe /install ../extension.zxp
