#!/bin/bash

msg=${1:-"commit this"}
git add .
git commit -m "$msg"
git push origin main
