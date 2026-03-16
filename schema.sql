create table users(
  id serial primary key,
  username varchar(50) unique not null,
  password varchar(255) not null,
  about_user varchar(150),
  profile_pic_url varchar(500),
  created_at timestamp default now()
)


CREATE TABLE contacts (
    id SERIAL PRIMARY KEY,
    owner_id INT REFERENCES users(id),
    contact_id INT REFERENCES users(id),
    nickname VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);


CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    participant_1 INT REFERENCES users(id),
    participant_2 INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);