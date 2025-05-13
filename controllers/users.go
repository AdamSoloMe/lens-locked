package controllers

import (
	"net/http"

	"github.com/AdamSoloMe/lenslocked/views"
)

type Users struct{
	Templates struct{
		New views.Template
	}
}


func (u Users) New(w http.ResponseWriter,r *http.Request){
	//will use view to render 
	u.Templates.New.ExecuteTemplate(w,nil)
}