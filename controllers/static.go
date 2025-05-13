package controllers

import (
	"html/template"
	"net/http"
)


func StaticHandler(tpl Template) http.HandlerFunc{ //replacing views.template
	return func(w http.ResponseWriter, r *http.Request)  {
		tpl.ExecuteTemplate(w,nil) //captialized functions means they are public if not captial it means that they are package private 
		
	}
}

func FAQ(tpl Template)  http.HandlerFunc{ //replacing views.template
	questions:= []struct{
		Question string
		Answer template.HTML
	}{
		{
		Question: "Is there a free version?",
		Answer:  "Yes! we offer a free trial for 30 days on any paid plans",
	},{
		Question:"What are your support hours? ",
		Answer: "We have support staff answering emails,on weekends 24/7,though response time may be a bit slower on weekends.",
	},
	{
		Question: "How do I contact support?",
		Answer: `Email us - <a href="mailto:support@lenslocked.com">support@lenslocked.com</a>`,

	},
}
	return func(w http.ResponseWriter, r *http.Request) {
		tpl.ExecuteTemplate(w, questions)
	}
}