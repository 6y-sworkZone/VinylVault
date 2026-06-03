from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, desc
from typing import List, Optional
from datetime import date, datetime
import os
import shutil
from pydantic import BaseModel
import httpx

from models import (
    get_db, Record, Track, Tag, RecordTag, TrackTag,
    PriceHistory, PlayRecord, Playlist, PlaylistItem,
    Device, MaintenanceRecord, Review, Event, ExchangeOffer
)

app = FastAPI(title="黑胶唱片收藏管理系统", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads/covers", exist_ok=True)
os.makedirs("uploads/inners", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


class RecordCreate(BaseModel):
    album_name: str
    artist: str
    release_year: Optional[int] = None
    label: Optional[str] = None
    catalog_number: Optional[str] = None
    genre: Optional[str] = None
    country: Optional[str] = None
    media_format: Optional[str] = None
    condition: Optional[str] = None
    purchase_price: Optional[float] = None
    current_market_price: Optional[float] = None
    personal_notes: Optional[str] = None
    version_notes: Optional[str] = None
    is_wishlist: bool = False
    wishlist_expected_price: Optional[float] = None


class RecordUpdate(BaseModel):
    album_name: Optional[str] = None
    artist: Optional[str] = None
    release_year: Optional[int] = None
    label: Optional[str] = None
    catalog_number: Optional[str] = None
    genre: Optional[str] = None
    country: Optional[str] = None
    media_format: Optional[str] = None
    condition: Optional[str] = None
    purchase_price: Optional[float] = None
    current_market_price: Optional[float] = None
    personal_notes: Optional[str] = None
    version_notes: Optional[str] = None
    is_wishlist: Optional[bool] = None
    wishlist_expected_price: Optional[float] = None


class TrackCreate(BaseModel):
    record_id: int
    side: str
    track_number: int
    title: str
    duration: Optional[int] = None
    notes: Optional[str] = None


class TagCreate(BaseModel):
    name: str
    color: str = "#3b82f6"
    tag_type: str = "general"


class PlayRecordCreate(BaseModel):
    record_id: int
    play_date: Optional[date] = None
    side_played: Optional[str] = None
    rating: Optional[float] = None
    scene: Optional[str] = None
    notes: Optional[str] = None


class PriceHistoryCreate(BaseModel):
    record_id: int
    price: float
    source: Optional[str] = None


class DeviceCreate(BaseModel):
    name: str
    brand: Optional[str] = None
    device_type: str
    purchase_date: Optional[date] = None
    purchase_price: Optional[float] = None
    condition: Optional[str] = None
    notes: Optional[str] = None
    is_wishlist: bool = False


class ReviewCreate(BaseModel):
    record_id: int
    user_name: str = "我"
    rating: float
    content: Optional[str] = None


class PlaylistCreate(BaseModel):
    name: str
    description: Optional[str] = None


class EventCreate(BaseModel):
    title: str
    event_type: str
    event_date: date
    location: Optional[str] = None
    description: Optional[str] = None
    is_attending: bool = False


@app.get("/")
def read_root():
    return {"message": "黑胶唱片收藏管理系统 API", "docs": "/docs"}


@app.post("/records/", response_model=dict)
def create_record(record: RecordCreate, db: Session = Depends(get_db)):
    existing = db.query(Record).filter(
        and_(
            Record.artist == record.artist,
            Record.album_name == record.album_name,
            Record.is_wishlist == record.is_wishlist
        )
    ).first()
    if existing and not record.version_notes:
        raise HTTPException(status_code=400, detail="该唱片已存在，如有不同版本请填写version_notes")

    db_record = Record(**record.dict())
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return {"id": db_record.id, **record.dict()}


@app.get("/records/check-duplicate")
def check_duplicate(artist: str, album_name: str, db: Session = Depends(get_db)):
    duplicates = db.query(Record).filter(
        and_(
            Record.artist.ilike(f"%{artist}%"),
            Record.album_name.ilike(f"%{album_name}%"),
            Record.is_wishlist == False
        )
    ).all()
    return {
        "is_duplicate": len(duplicates) > 0,
        "duplicates": [{"id": r.id, "album_name": r.album_name, "artist": r.artist, "version_notes": r.version_notes} for r in duplicates]
    }


@app.get("/records/", response_model=List[dict])
def get_records(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    artist: Optional[str] = None,
    genre: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    condition: Optional[str] = None,
    is_wishlist: Optional[bool] = False,
    db: Session = Depends(get_db)
):
    query = db.query(Record).filter(Record.is_wishlist == is_wishlist)

    if search:
        query = query.filter(
            or_(
                Record.album_name.ilike(f"%{search}%"),
                Record.artist.ilike(f"%{search}%"),
                Record.label.ilike(f"%{search}%")
            )
        )
    if artist:
        query = query.filter(Record.artist.ilike(f"%{artist}%"))
    if genre:
        query = query.filter(Record.genre == genre)
    if year_min:
        query = query.filter(Record.release_year >= year_min)
    if year_max:
        query = query.filter(Record.release_year <= year_max)
    if condition:
        query = query.filter(Record.condition == condition)

    records = query.offset(skip).limit(limit).all()
    return [
        {
            "id": r.id,
            "album_name": r.album_name,
            "artist": r.artist,
            "release_year": r.release_year,
            "genre": r.genre,
            "cover_image": r.cover_image,
            "condition": r.condition,
            "current_market_price": r.current_market_price
        }
        for r in records
    ]


@app.get("/records/{record_id}", response_model=dict)
def get_record(record_id: int, db: Session = Depends(get_db)):
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="唱片不存在")

    tracks = db.query(Track).filter(Track.record_id == record_id).order_by(Track.side, Track.track_number).all()
    total_duration = sum(t.duration or 0 for t in tracks)

    return {
        "id": record.id,
        "album_name": record.album_name,
        "artist": record.artist,
        "release_year": record.release_year,
        "label": record.label,
        "catalog_number": record.catalog_number,
        "genre": record.genre,
        "country": record.country,
        "media_format": record.media_format,
        "condition": record.condition,
        "purchase_price": record.purchase_price,
        "current_market_price": record.current_market_price,
        "cover_image": record.cover_image,
        "inner_sleeve_image": record.inner_sleeve_image,
        "personal_notes": record.personal_notes,
        "version_notes": record.version_notes,
        "total_duration": total_duration,
        "tracks": [
            {
                "id": t.id,
                "side": t.side,
                "track_number": t.track_number,
                "title": t.title,
                "duration": t.duration,
                "play_count": t.play_count,
                "rating": t.rating,
                "notes": t.notes
            }
            for t in tracks
        ]
    }


@app.put("/records/{record_id}", response_model=dict)
def update_record(record_id: int, record: RecordUpdate, db: Session = Depends(get_db)):
    db_record = db.query(Record).filter(Record.id == record_id).first()
    if not db_record:
        raise HTTPException(status_code=404, detail="唱片不存在")

    for key, value in record.dict(exclude_unset=True).items():
        setattr(db_record, key, value)

    db.commit()
    db.refresh(db_record)
    return {"id": db_record.id, "message": "更新成功"}


@app.delete("/records/{record_id}")
def delete_record(record_id: int, db: Session = Depends(get_db)):
    db_record = db.query(Record).filter(Record.id == record_id).first()
    if not db_record:
        raise HTTPException(status_code=404, detail="唱片不存在")
    db.delete(db_record)
    db.commit()
    return {"message": "删除成功"}


@app.post("/records/{record_id}/upload-cover")
def upload_cover(record_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="唱片不存在")

    file_ext = os.path.splitext(file.filename)[1]
    file_path = f"uploads/covers/{record_id}_{datetime.now().timestamp()}{file_ext}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    record.cover_image = f"/{file_path}"
    db.commit()
    return {"cover_image": record.cover_image}


@app.post("/records/{record_id}/upload-inner")
def upload_inner_sleeve(record_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="唱片不存在")

    file_ext = os.path.splitext(file.filename)[1]
    file_path = f"uploads/inners/{record_id}_{datetime.now().timestamp()}{file_ext}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    record.inner_sleeve_image = f"/{file_path}"
    db.commit()
    return {"inner_sleeve_image": record.inner_sleeve_image}


@app.post("/tracks/", response_model=dict)
def create_track(track: TrackCreate, db: Session = Depends(get_db)):
    db_track = Track(**track.dict())
    db.add(db_track)
    db.commit()
    db.refresh(db_track)
    return {"id": db_track.id, **track.dict()}


@app.post("/tracks/{track_id}/play")
def increment_play_count(track_id: int, db: Session = Depends(get_db)):
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="曲目不存在")
    track.play_count += 1
    db.commit()
    return {"play_count": track.play_count}


@app.get("/tracks/top")
def get_top_tracks(limit: int = 10, db: Session = Depends(get_db)):
    tracks = db.query(Track).order_by(desc(Track.play_count), desc(Track.rating)).limit(limit).all()
    return [
        {
            "id": t.id,
            "title": t.title,
            "artist": t.record.artist if t.record else "未知",
            "album": t.record.album_name if t.record else "未知",
            "play_count": t.play_count,
            "rating": t.rating
        }
        for t in tracks
    ]


@app.get("/tags/", response_model=List[dict])
def get_tags(tag_type: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Tag)
    if tag_type:
        query = query.filter(Tag.tag_type == tag_type)
    tags = query.all()
    return [{"id": t.id, "name": t.name, "color": t.color, "tag_type": t.tag_type} for t in tags]


@app.post("/tags/", response_model=dict)
def create_tag(tag: TagCreate, db: Session = Depends(get_db)):
    existing = db.query(Tag).filter(Tag.name == tag.name).first()
    if existing:
        return {"id": existing.id, "name": existing.name, "color": existing.color}
    db_tag = Tag(**tag.dict())
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return {"id": db_tag.id, **tag.dict()}


@app.post("/records/{record_id}/tags/{tag_id}")
def add_record_tag(record_id: int, tag_id: int, db: Session = Depends(get_db)):
    existing = db.query(RecordTag).filter_by(record_id=record_id, tag_id=tag_id).first()
    if existing:
        return {"message": "标签已存在"}
    db.add(RecordTag(record_id=record_id, tag_id=tag_id))
    db.commit()
    return {"message": "标签添加成功"}


@app.post("/play-records/", response_model=dict)
def create_play_record(play_record: PlayRecordCreate, db: Session = Depends(get_db)):
    if not play_record.play_date:
        play_record.play_date = date.today()
    db_play = PlayRecord(**play_record.dict())
    db.add(db_play)
    db.commit()
    db.refresh(db_play)

    tracks = db.query(Track).filter(Track.record_id == play_record.record_id).all()
    for track in tracks:
        if not play_record.side_played or track.side == play_record.side_played:
            track.play_count += 1
    db.commit()

    return {"id": db_play.id, **play_record.dict()}


@app.get("/play-records/calendar")
def get_play_calendar(year: int, month: int, db: Session = Depends(get_db)):
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    records = db.query(PlayRecord).filter(
        and_(PlayRecord.play_date >= start_date, PlayRecord.play_date < end_date)
    ).all()

    calendar = {}
    for r in records:
        day = r.play_date.day
        if day not in calendar:
            calendar[day] = []
        calendar[day].append({
            "id": r.id,
            "record_id": r.record_id,
            "album_name": r.record.album_name if r.record else "未知",
            "side_played": r.side_played,
            "scene": r.scene
        })
    return calendar


@app.get("/play-records/top-records")
def get_top_played_records(limit: int = 10, db: Session = Depends(get_db)):
    result = db.query(
        Record.id,
        Record.album_name,
        Record.artist,
        func.count(PlayRecord.id).label('play_count')
    ).join(PlayRecord).group_by(Record.id).order_by(desc('play_count')).limit(limit).all()

    return [
        {"id": r.id, "album_name": r.album_name, "artist": r.artist, "play_count": r.play_count}
        for r in result
    ]


@app.get("/play-records/scene-analysis")
def get_scene_analysis(db: Session = Depends(get_db)):
    result = db.query(
        PlayRecord.scene,
        Record.genre,
        func.count(PlayRecord.id).label('count')
    ).join(Record).group_by(PlayRecord.scene, Record.genre).all()

    analysis = {}
    for scene, genre, count in result:
        if scene not in analysis:
            analysis[scene] = {}
        analysis[scene][genre] = count
    return analysis


@app.post("/price-history/", response_model=dict)
def create_price_history(price_data: PriceHistoryCreate, db: Session = Depends(get_db)):
    db_price = PriceHistory(**price_data.dict())
    db.add(db_price)

    record = db.query(Record).filter(Record.id == price_data.record_id).first()
    if record:
        record.current_market_price = price_data.price
        record.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_price)
    return {"id": db_price.id, **price_data.dict()}


@app.get("/price-history/{record_id}", response_model=List[dict])
def get_price_history(record_id: int, db: Session = Depends(get_db)):
    history = db.query(PriceHistory).filter(PriceHistory.record_id == record_id).order_by(PriceHistory.record_date).all()
    return [
        {"id": h.id, "price": h.price, "record_date": h.record_date, "source": h.source}
        for h in history
    ]


@app.get("/statistics/overview")
def get_statistics_overview(db: Session = Depends(get_db)):
    total_records = db.query(Record).filter(Record.is_wishlist == False).count()
    wishlist_count = db.query(Record).filter(Record.is_wishlist == True).count()

    total_value = db.query(func.sum(Record.current_market_price)).filter(Record.is_wishlist == False).scalar() or 0
    total_investment = db.query(func.sum(Record.purchase_price)).filter(Record.is_wishlist == False).scalar() or 0

    genre_stats = db.query(
        Record.genre,
        func.count(Record.id).label('count')
    ).filter(Record.is_wishlist == False).group_by(Record.genre).all()

    year_stats = db.query(
        Record.release_year,
        func.count(Record.id).label('count')
    ).filter(Record.is_wishlist == False, Record.release_year.isnot(None)).group_by(Record.release_year).order_by(Record.release_year).all()

    return {
        "total_records": total_records,
        "wishlist_count": wishlist_count,
        "total_value": round(total_value, 2),
        "total_investment": round(total_investment, 2),
        "roi": round(((total_value - total_investment) / total_investment * 100), 2) if total_investment > 0 else 0,
        "genre_stats": {g: c for g, c in genre_stats if g},
        "year_stats": {str(y): c for y, c in year_stats if y}
    }


@app.get("/statistics/top-gainers")
def get_top_gainers(limit: int = 10, db: Session = Depends(get_db)):
    records = db.query(Record).filter(
        and_(Record.is_wishlist == False, Record.purchase_price > 0, Record.current_market_price > 0)
    ).all()

    gainers = []
    for r in records:
        gain = r.current_market_price - r.purchase_price
        gain_percent = (gain / r.purchase_price) * 100
        gainers.append({
            "id": r.id,
            "album_name": r.album_name,
            "artist": r.artist,
            "purchase_price": r.purchase_price,
            "current_price": r.current_market_price,
            "gain": round(gain, 2),
            "gain_percent": round(gain_percent, 2)
        })

    gainers.sort(key=lambda x: x["gain_percent"], reverse=True)
    return gainers[:limit]


@app.get("/records/grouped")
def get_records_grouped(group_by: str = Query(..., pattern="^(genre|year|label|country)$"), db: Session = Depends(get_db)):
    records = db.query(Record).filter(Record.is_wishlist == False).all()
    groups = {}

    for r in records:
        key = getattr(r, "release_year" if group_by == "year" else group_by)
        if not key:
            key = "未知"
        if key not in groups:
            groups[key] = []
        groups[key].append({
            "id": r.id,
            "album_name": r.album_name,
            "artist": r.artist,
            "cover_image": r.cover_image
        })

    return groups


@app.get("/records/wall")
def get_records_wall(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    records = db.query(Record).filter(
        and_(Record.is_wishlist == False, Record.cover_image.isnot(None))
    ).offset(skip).limit(limit).all()
    return [
        {"id": r.id, "album_name": r.album_name, "artist": r.artist, "cover_image": r.cover_image}
        for r in records
    ]


@app.post("/devices/", response_model=dict)
def create_device(device: DeviceCreate, db: Session = Depends(get_db)):
    db_device = Device(**device.dict())
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    return {"id": db_device.id, **device.dict()}


@app.get("/devices/", response_model=List[dict])
def get_devices(device_type: Optional[str] = None, is_wishlist: bool = False, db: Session = Depends(get_db)):
    query = db.query(Device).filter(Device.is_wishlist == is_wishlist)
    if device_type:
        query = query.filter(Device.device_type == device_type)
    devices = query.all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "brand": d.brand,
            "device_type": d.device_type,
            "purchase_date": d.purchase_date,
            "purchase_price": d.purchase_price,
            "condition": d.condition,
            "usage_hours": d.usage_hours
        }
        for d in devices
    ]


@app.post("/reviews/", response_model=dict)
def create_review(review: ReviewCreate, db: Session = Depends(get_db)):
    db_review = Review(**review.dict())
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return {"id": db_review.id, **review.dict()}


@app.get("/reviews/", response_model=List[dict])
def get_reviews(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    reviews = db.query(Review).order_by(desc(Review.created_at)).offset(skip).limit(limit).all()
    return [
        {
            "id": r.id,
            "record_id": r.record_id,
            "album_name": r.record.album_name if r.record else "未知",
            "user_name": r.user_name,
            "rating": r.rating,
            "content": r.content,
            "created_at": r.created_at
        }
        for r in reviews
    ]


@app.post("/playlists/", response_model=dict)
def create_playlist(playlist: PlaylistCreate, db: Session = Depends(get_db)):
    db_playlist = Playlist(**playlist.dict())
    db.add(db_playlist)
    db.commit()
    db.refresh(db_playlist)
    return {"id": db_playlist.id, **playlist.dict()}


@app.get("/playlists/", response_model=List[dict])
def get_playlists(db: Session = Depends(get_db)):
    playlists = db.query(Playlist).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "item_count": len(p.items)
        }
        for p in playlists
    ]


@app.post("/events/", response_model=dict)
def create_event(event: EventCreate, db: Session = Depends(get_db)):
    db_event = Event(**event.dict())
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return {"id": db_event.id, **event.dict()}


@app.get("/events/", response_model=List[dict])
def get_events(upcoming_only: bool = True, db: Session = Depends(get_db)):
    query = db.query(Event)
    if upcoming_only:
        query = query.filter(Event.event_date >= date.today())
    events = query.order_by(Event.event_date).all()
    return [
        {
            "id": e.id,
            "title": e.title,
            "event_type": e.event_type,
            "event_date": e.event_date,
            "location": e.location,
            "description": e.description,
            "is_attending": e.is_attending
        }
        for e in events
    ]


@app.get("/discogs/search")
async def search_discogs(
    query: str,
    search_type: str = Query("release", pattern="^(release|artist)$"),
    db: Session = Depends(get_db)
):
    url = f"https://api.discogs.com/database/search?q={query}&type={search_type}"
    headers = {"User-Agent": "VinylVault/1.0"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Discogs API 请求失败")
        data = response.json()

    results = []
    for item in data.get("results", [])[:20]:
        results.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "artist": item.get("artist"),
            "year": item.get("year"),
            "label": item.get("label", [None])[0] if item.get("label") else None,
            "genre": item.get("genre", [None])[0] if item.get("genre") else None,
            "country": item.get("country"),
            "cover_image": item.get("cover_image"),
            "uri": item.get("uri")
        })

    return results


@app.post("/discogs/import/{discogs_id}")
async def import_from_discogs(discogs_id: int, db: Session = Depends(get_db)):
    url = f"https://api.discogs.com/releases/{discogs_id}"
    headers = {"User-Agent": "VinylVault/1.0"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Discogs API 请求失败")
        data = response.json()

    artist = data.get("artists", [{}])[0].get("name", "未知艺术家") if data.get("artists") else "未知艺术家"
    album_name = data.get("title", "未知专辑")

    existing = db.query(Record).filter(
        and_(Record.discogs_id == str(discogs_id), Record.is_wishlist == False)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"该唱片已存在: ID {existing.id}")

    record = Record(
        album_name=album_name,
        artist=artist,
        release_year=data.get("year"),
        label=data.get("labels", [{}])[0].get("name") if data.get("labels") else None,
        catalog_number=data.get("labels", [{}])[0].get("catno") if data.get("labels") else None,
        genre=data.get("genres", [None])[0] if data.get("genres") else None,
        country=data.get("country"),
        media_format=data.get("formats", [{}])[0].get("name") if data.get("formats") else None,
        discogs_id=str(discogs_id)
    )
    db.add(record)
    db.flush()

    for track in data.get("tracklist", []):
        duration_str = track.get("duration", "0:00")
        try:
            minutes, seconds = map(int, duration_str.split(":"))
            duration = minutes * 60 + seconds
        except:
            duration = 0

        position = track.get("position", "")
        side = position[0] if position and position[0].isalpha() else "A"
        try:
            track_num = int(''.join(filter(str.isdigit, position))) if position else 0
        except:
            track_num = 0

        db.add(Track(
            record_id=record.id,
            side=side,
            track_number=track_num,
            title=track.get("title", "未知曲目"),
            duration=duration
        ))

    db.commit()
    db.refresh(record)

    return {"record_id": record.id, "album_name": album_name, "artist": artist, "tracks_imported": len(data.get("tracklist", []))}


@app.get("/year-summary/{year}")
def get_year_summary(year: int, db: Session = Depends(get_db)):
    start_date = date(year, 1, 1)
    end_date = date(year + 1, 1, 1)

    records_added = db.query(Record).filter(
        and_(Record.created_at >= start_date, Record.created_at < end_date, Record.is_wishlist == False)
    ).count()

    total_spent = db.query(func.sum(Record.purchase_price)).filter(
        and_(Record.created_at >= start_date, Record.created_at < end_date, Record.is_wishlist == False)
    ).scalar() or 0

    play_count = db.query(PlayRecord).filter(
        and_(PlayRecord.play_date >= start_date, PlayRecord.play_date < end_date)
    ).count()

    top_genres = db.query(
        Record.genre,
        func.count(Record.id).label('count')
    ).filter(
        and_(Record.created_at >= start_date, Record.created_at < end_date, Record.is_wishlist == False)
    ).group_by(Record.genre).order_by(desc('count')).limit(5).all()

    return {
        "year": year,
        "records_added": records_added,
        "total_spent": round(total_spent, 2),
        "play_count": play_count,
        "top_genres": {g: c for g, c in top_genres if g}
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
