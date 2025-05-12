package controllers

import ("net/http"
 "github.com/AdamSoloMe/lenslocked/views")


func StaticHandler(tpl views.Template) http.HandlerFunc{
	return func(w http.ResponseWriter, r *http.Request)  {
		tpl.ExecuteTemplate(w,nil) //captialized functions means they are public if not captial it means that they are package private 
		
	}
}