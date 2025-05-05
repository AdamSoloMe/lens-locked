package main

import (
	"fmt"
	"net/http"
)

//The net/http package in the standard library even has a type for it - http.HandlerFunc.

//basic routing

func (router Router) ServeHttp(w http.ResponseWriter, r *http.Request){
	switch r.URL.Path{
	case "/":
		handlerFunc(w,r)
	case "/contact":
		contactHandler(w,r)
	default:
		http.Error(w,"Page Not found",http.StatusNotFound)
	}
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
	fmt.Fprint(w,"<h1> Contact page</h1><p>To get in touch email me at</p>")


}



func main(){
	//how to register our handler function is with http.handlerfunc
	http.HandleFunc("/",handlerFunc)//first pass in the pattern/paths that this function will handle then the function
	http.HandleFunc("/contact",contactHandler)

	//good dev indicator that the server is running
	fmt.Println("Starting Server on 3000")
	http.ListenAndServe(":3000",nil)//this function setups and starts the server to listern on port 3000

	//routing deciding which pages to show the user 
}