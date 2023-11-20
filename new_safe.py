from app import app, CurrentCode, desc, scheduler, db, sse

def update_code():
    with app.app_context():
        last_code_id = CurrentCode.query.order_by(desc(CurrentCode.id)).limit(1).first()

        if not last_code_id.is_updated:
            print("sse")
            sse.publish({"status": "new_code"}, type='updates')
        else:
            print("sse else")
            sse.publish({"status": "keep_alive"}, type='updates')
        last_code_id.is_updated = True
        db.session.commit()

update_code()
