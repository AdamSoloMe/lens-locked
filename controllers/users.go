package controllers

import (
	"fmt"
	"net/http"
)

type Users struct{
	Templates struct{
		New Template //replacing views.template
	}
}


func (u Users) New(w http.ResponseWriter,r *http.Request){
	//will use view to render 
	u.Templates.New.ExecuteTemplate(w,nil)
}

func (u Users) CreateUser( w http.ResponseWriter, r *http.Request){
	err:= r.ParseForm()
	if err !=nil {
		http.Error(w,err.Error(),http.StatusBadRequest)
		return
	}
	fmt.Fprint(w, "Email: ",r.FormValue("email"))
	fmt.Fprint(w, "Password: ",r.FormValue("password"))

}