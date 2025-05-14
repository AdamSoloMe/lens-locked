package main

import (
	"database/sql"
	"fmt"
	"html/template"
	"os"

	_ "github.com/jackc/pgx/v4/stdlib"
)

type User struct{
	Name string

}

//making a postgres config type/struct to connect to our database instead of hardcoded string
type PostGresConfig struct{
	Host string
	Port string
	User string
	Password string
	Database string
	SSLMode string
}

//function to establish the connection to the database

func (cfg PostGresConfig) String() string{
	return fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=%s",cfg.Host,cfg.Port,cfg.User,cfg.Password,cfg.Database,cfg.SSLMode)
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
	//old
	// db,err:=sql.Open("pgx","host=localhost port=5432 user=baloo password=junglebook dbname=lenslocked sslmode=disable")
	// if err !=nil{
	// 	panic(err)
	// }
	// defer db.Close()
	
	// err=db.Ping()
	// if err !=nil{
	// 	panic(err)
	// }
	// fmt.Println("connected")

	cfg := PostGresConfig {
		Host: "localhost",
		Port: "5432",
		User: "baloo",
		Password: "junglebook",
		Database: "lenslocked",
		SSLMode: "disable",

	}
	db,err:=sql.Open("pgx",cfg.String())
	if err !=nil{
		panic(err)
	}
	defer db.Close()
	
	err=db.Ping()
	if err !=nil{
		panic(err)
	}
	fmt.Println("connected")


	numbers:= []int{10,20,30}
	for index, number := range numbers{
		fmt.Println(index,number)
	}
	
}