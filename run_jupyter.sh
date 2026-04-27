JUPYTER_PORT=8901
jupyter lab --ip=0.0.0.0 --port=${JUPYTER_PORT} --no-browser --allow-root --NotebookApp.token='' --NotebookApp.password='' --NotebookApp.allow_origin='*' --ServerApp.disable_check_xsrf=True
