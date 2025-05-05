package main

import (
	"fmt"
	"net/http"

	"github.com/go-chi/chi/v5"
)

func homeHandler(w http.ResponseWriter, r *http.Request){
	w.Header().Set("Content-Type","text/html: charset=utf-8")
	fmt.Fprint(w,"<h1.Welcome to my awesome site!</h1>")
}

//default status code is 200
//http request is not an interface but a pointer to a struct type of Http request
//the response writer is an interface allows for mulitpe impelemntaions and also to test it easier
func handlerFunc(w http.ResponseWriter, r *http.Request){
	//explictily setting content type
	w.Header().Set("Content-Type","text/html; charset=utf-8")
	fmt.Fprint(w,"<h1>welcome to my Awsome Site </h1>")//go print statement but allows to control where to print to
}

func contactHandler(w http.ResponseWriter,r *http.Request){
	w.Header().Set("Content-Type","text/html; charset=utf-8")
	fmt.Fprint(w,"<h1> Contact page</h1><p>To get in touch email me at <a href=\"mailto:mrfanstatic2005@gmail.com\"></a> </p>")

}

func faqHandler(w http.ResponseWriter, r *http.Request){
	w.Header().Set("Contet-Type","text/html; charset=utf-8")
	fmt.Fprint(w, `<h1> FAQ Page </h1>
	<ul>
	<li><b> Is there a free version> </b> Yes! we offer a free trial for 30 days on any paid plans.</li>
	<li><b> What are your support hours? </b> We have support staff answering emails on weekends 24/7,
	though response time may be a bit slower on weekends.</li>
	<li> <b> How do I contact support? </b> Email us - <a href="mailto:support@lenslocked.com">support@lenslocked.com</a></li>
	</ul>
	`)

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
	http.ListenAndServe(":3000",nil)//this function setups and starts the server to listern on port 3000

	//routing deciding which pages to show the user 
}