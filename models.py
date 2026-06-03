from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./vinyl_vault.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Record(Base):
    __tablename__ = "records"

    id = Column(Integer, primary_key=True, index=True)
    album_name = Column(String, index=True)
    artist = Column(String, index=True)
    release_year = Column(Integer)
    label = Column(String)
    catalog_number = Column(String, index=True)
    genre = Column(String, index=True)
    country = Column(String)
    media_format = Column(String)
    condition = Column(String)
    purchase_price = Column(Float)
    current_market_price = Column(Float)
    cover_image = Column(String)
    inner_sleeve_image = Column(String)
    personal_notes = Column(Text)
    discogs_id = Column(String)
    version_notes = Column(String)
    is_wishlist = Column(Boolean, default=False)
    wishlist_expected_price = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tracks = relationship("Track", back_populates="record", cascade="all, delete-orphan")
    price_history = relationship("PriceHistory", back_populates="record", cascade="all, delete-orphan")
    play_records = relationship("PlayRecord", back_populates="record")
    tags = relationship("RecordTag", back_populates="record", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="record")


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("records.id"))
    side = Column(String)
    track_number = Column(Integer)
    title = Column(String)
    duration = Column(Integer)
    play_count = Column(Integer, default=0)
    rating = Column(Float)
    notes = Column(Text)

    record = relationship("Record", back_populates="tracks")
    tags = relationship("TrackTag", back_populates="track", cascade="all, delete-orphan")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    color = Column(String, default="#3b82f6")
    tag_type = Column(String)

    record_tags = relationship("RecordTag", back_populates="tag")
    track_tags = relationship("TrackTag", back_populates="tag")


class RecordTag(Base):
    __tablename__ = "record_tags"

    id = Column(Integer, primary_key=True)
    record_id = Column(Integer, ForeignKey("records.id"))
    tag_id = Column(Integer, ForeignKey("tags.id"))

    record = relationship("Record", back_populates="tags")
    tag = relationship("Tag", back_populates="record_tags")


class TrackTag(Base):
    __tablename__ = "track_tags"

    id = Column(Integer, primary_key=True)
    track_id = Column(Integer, ForeignKey("tracks.id"))
    tag_id = Column(Integer, ForeignKey("tags.id"))

    track = relationship("Track", back_populates="tags")
    tag = relationship("Tag", back_populates="track_tags")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("records.id"))
    price = Column(Float)
    record_date = Column(Date, default=datetime.utcnow)
    source = Column(String)

    record = relationship("Record", back_populates="price_history")


class PlayRecord(Base):
    __tablename__ = "play_records"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("records.id"))
    play_date = Column(Date, default=datetime.utcnow)
    side_played = Column(String)
    rating = Column(Float)
    scene = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    record = relationship("Record", back_populates="play_records")


class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("PlaylistItem", back_populates="playlist", cascade="all, delete-orphan")


class PlaylistItem(Base):
    __tablename__ = "playlist_items"

    id = Column(Integer, primary_key=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id"))
    record_id = Column(Integer, ForeignKey("records.id"))
    track_id = Column(Integer, ForeignKey("tracks.id"))
    order = Column(Integer)

    playlist = relationship("Playlist", back_populates="items")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    brand = Column(String)
    device_type = Column(String)
    purchase_date = Column(Date)
    purchase_price = Column(Float)
    condition = Column(String)
    usage_hours = Column(Float, default=0)
    notes = Column(Text)
    is_wishlist = Column(Boolean, default=False)

    maintenance_records = relationship("MaintenanceRecord", back_populates="device", cascade="all, delete-orphan")


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"))
    maintenance_type = Column(String)
    maintenance_date = Column(Date)
    notes = Column(Text)
    next_maintenance_date = Column(Date)

    device = relationship("Device", back_populates="maintenance_records")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("records.id"))
    user_name = Column(String, default="我")
    rating = Column(Float)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    record = relationship("Record", back_populates="reviews")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    collection_goal = Column(Integer, default=500)
    created_at = Column(DateTime, default=datetime.utcnow)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    event_type = Column(String)
    event_date = Column(Date)
    location = Column(String)
    description = Column(Text)
    is_attending = Column(Boolean, default=False)


class ExchangeOffer(Base):
    __tablename__ = "exchange_offers"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("records.id"))
    offer_type = Column(String)
    description = Column(Text)
    contact_info = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
