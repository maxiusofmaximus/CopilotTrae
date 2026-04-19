mod commands;

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();

    match commands::run(&args) {
        Ok(stdout) => println!("{stdout}"),
        Err(message) => {
            eprintln!("{message}");
            std::process::exit(1);
        }
    }
}
