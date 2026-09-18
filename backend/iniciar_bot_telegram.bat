@echo off
REM Corre el bot de Telegram (long-polling) y lo reinicia solo si se cae
REM (ej. se pierde internet un momento). Sin esto, el bot de Telegram deja
REM de responder en silencio hasta que alguien note que no contesta y
REM vuelva a escribir el comando a mano en una terminal.
REM
REM Para que arranque solo con Windows: Programador de tareas -> Crear
REM tarea basica -> Desencadenador "Al iniciar sesion" -> Accion "Iniciar
REM un programa" -> apuntar a este archivo .bat.

cd /d "%~dp0"
call ..\.venv\Scripts\activate.bat

:loop
echo [%date% %time%] Iniciando bot de Telegram...
python manage.py telegram_bot
echo [%date% %time%] El bot se detuvo (codigo %errorlevel%). Reintentando en 5s...
timeout /t 5 /nobreak >nul
goto loop
