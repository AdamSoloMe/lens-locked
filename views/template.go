package views

import (
	"fmt"
	"html/template"
	"log"
	"net/http"
)

func ParseTemplate(filepath string) (Template, error){
	tpl,err := template.ParseFiles(filepath)
	if err != nil{ //placeholder for when I enventually put in parsing errors
		return Template{},fmt.Errorf("parsing template: %w",err)
	} 
	return Template{
		htmlTpl: tpl,
	},nil
}

type Template struct{
	htmlTpl *template.Template
}



func (t Template) ExecuteTemplate(w http.ResponseWriter , data interface{}){
	w.Header().Set("Contet-Type","text/html; charset=utf-8")
	err:= t.htmlTpl.Execute(w,data)
	if err !=nil{
		log.Printf("executing template: %v",err)
		http.Error(w,"There was an error executing the template ", http.StatusInternalServerError)
		return
	}
}
