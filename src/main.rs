use indoc::indoc;

use teloxide::{dispatching::dialogue::InMemStorage, prelude::*};

const HELLO: &'static str = indoc! {"
Вы можете предложить обьявление в барахолку Рога и Копыта, нажав на кнопку ниже:
"};
const PROVIDE_THE_DEVICE_NAME: &'static str = indoc! {"
Укажите полное название девайса, его цвет и вид:
"};
const PROVIDE_THE_STATE: &'static str = indoc! {"
Укажите состояние по пятибалльной шкале:
"};
const PROVIDE_THE_COMPONENTS: &'static str = indoc! {"
Укажите, какие комплектующие у вас от него есть:
"};
const PROVIDE_THE_PRICE: &'static str = indoc! {"
Укажите цену:
"};
const CHOOSE_THE_MEETING_METHOD: &'static str = indoc! {"
Как вы хотите организовать встречу?
"};
const MEETING_METHOD_NAMES: [&'static str; 2] = ["Самовывоз", "Можем встретиться"];
const PROVIDE_THE_IMAGES: &'static str = indoc! {"
Предоставьте фотографии девайса:
"};
const PROVIDE_THE_ADDITIONAL_INFORMATION: &'static str = indoc! {"
Предоставьте дополнительную информацию (или нажмите на кнопку, если дополнительной информации нет):
"};

type MyDialogue = Dialogue<State, InMemStorage<State>>;
type HandlerResult = Result<(), Box<dyn std::error::Error + Send + Sync>>;

pub enum ReceivingType {

}

impl ReceivingType {
    pub fn from_string(s: &str) -> Result<Self, ()> {
        if s == ""
    }
}

#[derive(Default)]
pub enum State {
    #[default]
    Start,
    ReceiveDeviceName,
    ReceiveDeviceState { device_name: String },
    ReceiveDeviceComponents { device_name: String, device_state: String },
    ReceiveDevicePrice { device_name: String, device_state: String, device_components: String },
    ReceiveReceivingType { device_name: String, device_state: String, device_components: String },
    ReceiveDevicePhotos { device_name: String, device_state: String, device_components: String, receiving_type: ReceivingType },
    ReceiveAdditionalInformation { device_name: String, device_state: String, device_components: String, receiving_type: ReceivingType, additional_information: String },
}

#[tokio::main]
async fn main() {
    pretty_env_logger::init();
    log::info!("Starting!");

    let bot = Bot::new(std::fs::read_to_string("token.txt").unwrap());

    Dispatcher::builder(
        bot,
        Update::filter_message()
            .enter_dialogue::<Message, InMemStorage<State>, State>()
            .branch(dptree::case![State::Start].endpoint(start))
            .branch(dptree::case![State::ReceiveFullName].endpoint(receive_full_name))
            .branch(dptree::case![State::ReceiveAge { full_name }].endpoint(receive_age))
            .branch(
                dptree::case![State::ReceiveLocation { full_name, age }].endpoint(receive_location),
            ),
    )
    .dependencies(dptree::deps![InMemStorage::<State>::new()])
    .enable_ctrlc_handler()
    .build()
    .dispatch()
    .await;
}

async fn start(bot: Bot, dialogue: MyDialogue, msg: Message) -> HandlerResult {
    bot.send_message(msg.chat.id, "Let's start! What's your full name?")
        .await?;
    dialogue.update(State::ReceiveFullName).await?;
    Ok(())
}

async fn receive_full_name(bot: Bot, dialogue: MyDialogue, msg: Message) -> HandlerResult {
    match msg.text() {
        Some(text) => {
            bot.send_message(msg.chat.id, "How old are you?").await?;
            dialogue
                .update(State::ReceiveAge {
                    full_name: text.into(),
                })
                .await?;
        }
        None => {
            bot.send_message(msg.chat.id, "Send me plain text.").await?;
        }
    }

    Ok(())
}

async fn receive_age(
    bot: Bot,
    dialogue: MyDialogue,
    full_name: String, // Available from `State::ReceiveAge`.
    msg: Message,
) -> HandlerResult {
    match msg.text().map(|text| text.parse::<u8>()) {
        Some(Ok(age)) => {
            bot.send_message(msg.chat.id, "What's your location?")
                .await?;
            dialogue
                .update(State::ReceiveLocation { full_name, age })
                .await?;
        }
        _ => {
            bot.send_message(msg.chat.id, "Send me a number.").await?;
        }
    }

    Ok(())
}

async fn receive_location(
    bot: Bot,
    dialogue: MyDialogue,
    (full_name, age): (String, u8), // Available from `State::ReceiveLocation`.
    msg: Message,
) -> HandlerResult {
    match msg.text() {
        Some(location) => {
            let report = format!("Full name: {full_name}\nAge: {age}\nLocation: {location}");
            bot.send_message(msg.chat.id, report).await?;
            dialogue.exit().await?;
        }
        None => {
            bot.send_message(msg.chat.id, "Send me plain text.").await?;
        }
    }

    Ok(())
}
