package main

import (
	"fmt"
	"log"
	"net/http"
	"path/filepath"

    "github.com/AdamSoloMe/lenslocked/views"
	"github.com/go-chi/chi/v5"
)

func homeHandler(w http.ResponseWriter, r *http.Request){
	w.Header().Set("Content-Type","text/html; charset=utf-8")
	//how to avoid filepath issues 
	tplPath :=filepath.Join("templates","home.gohtml")
	executeTemplate(w,tplPath)

}


func contactHandler(w http.ResponseWriter, r *http.Request){
	w.Header().Set("Content-Type","text/html; charset=utf-8")
	//how to avoid filepath issues 
	tplPath :=filepath.Join("templates","contacts.gohtml")
	executeTemplate(w,tplPath)
}
//default status code is 200
//http request is not an interface but a pointer to a struct type of Http request
//the response writer is an interface allows for mulitpe impelemntaions and also to test it easier
// func handlerFunc(w http.ResponseWriter, r *http.Request){
// 	//explictily setting content type
// 	w.Header().Set("Content-Type","text/html; charset=utf-8")
// 	fmt.Fprint(w,"<h1> welcome to my Awsome Site </h1>")//go print statement but allows to control where to print to
// }

// func contactHandler(w http.ResponseWriter,r *http.Request){
// 	w.Header().Set("Content-Type","text/html; charset=utf-8")
// 	fmt.Fprint(w,"<h1> Contact page</h1><p>To get in touch email me at <a href=\"mailto:mrfanstatic2005@gmail.com\">mrfanstatic2005@gmail.com</a> </p>")

// }


func faqHandler(w http.ResponseWriter, r *http.Request){
	w.Header().Set("Contet-Type","text/html; charset=utf-8")
	//how to avoid filepath issues 
	tplPath :=filepath.Join("templates","faq.gohtml")
	executeTemplate(w,tplPath)
}

func executeTemplate(w http.ResponseWriter , filepath string){
	w.Header().Set("Contet-Type","text/html; charset=utf-8")
	t,err:= views.ParseTemplate(filepath)
	// tpl, err := template.ParseFiles(filepath)
	if err != nil{ //placeholder for when I enventually put in parsing errors
		log.Printf("Parising template: %v",err)
		http.Error(w,"There was an issue parsing this template", http.StatusInternalServerError)
		return
	}
	// viewTpl := views.Template{
	// 	HTMLTpl: tpl,
	// }
	t.ExecuteTemplate(w,nil)
}

func main(){
	//how to register our handler function is with http.handlerfunc
	// http.HandleFunc("/",handlerFunc)//first pass in the pattern/paths that this function will handle then the function
	// http.HandleFunc("/contact",contactHandler)

	//using chi 
	r :=chi.NewRouter() //How to setup New Chi Router
	r.Get("/",homeHandler)
	r.Get("/contact",contactHandler)
	r.Get("/faq",faqHandler)

	r.NotFound(func (w http.ResponseWriter, r *http.Request){
		http.Error(w,"Page not found",http.StatusNotFound)
		
	})

	//good dev indicator that the server is running
	fmt.Println("Starting Server on 3000")
	http.ListenAndServe(":3000",r)//this function setups and starts the server to listern on port 3000

	//routing deciding which pages to show the user 
}