package controllers

import(
	"net/http"
)

type Template interface{
	ExecuteTemplate(w http.ResponseWriter, data interface{})
}