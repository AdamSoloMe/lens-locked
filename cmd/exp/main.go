package main

import (
	"os"
	"html/template"
)

type User struct{
	Name string

}

func main(){
	t,err := template.ParseFiles("hello.gohtml")
	if err != nil{
		panic(err)
	}

	user := User{
		Name: "Reed Richards",
	}
	err=t.Execute(os.Stdout,user)
	if err !=nil{
		panic(err)
	}
}