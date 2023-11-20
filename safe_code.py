from app import app, CurrentCode, desc, CodeAd, image, db, User, SuccessfulCode, os, randint, sse, Timer


def check_and_update_code():
    all_ads = len(os.listdir("ads"))
    print("Update code")
    with app.app_context():
        with app.test_request_context('/generate-code', method='GET'):
            last_code_id = CurrentCode.query.order_by(desc(CurrentCode.id)).limit(1).first()

            latest_code_ad = CodeAd.query.order_by(desc(CodeAd.id)).limit(1).first()

            new_code = CurrentCode(current_code=str(randint(999999, 9999999)))
            image.write(str(new_code.current_code), 'out.png')
            db.session.add(new_code)
            db.session.commit()

            if latest_code_ad:
                new_ad_for_code = CodeAd(code_fk=new_code.id, ad_index=(latest_code_ad.ad_index + 1) % all_ads)
            else:
                new_ad_for_code = CodeAd(code_fk=new_code.id, ad_index=0)

            db.session.add(new_ad_for_code)

            if last_code_id:
                last_code_id = last_code_id.id

                for i in User.query.all():
                    if i.lives_remaining > 0:
                        i.lives_remaining -= 1

                db.session.commit()
                total_entries = SuccessfulCode.query.filter_by(current_code_fk=last_code_id).all()

                for i in total_entries:
                    print(i.user_fk)
                    User.query.get(i.user_fk).lives_remaining += 1
                    User.query.get(i.user_fk).status = "Continue"
                if len(total_entries) == 1:
                    User.query.get(total_entries[0].user_fk).status = "Continue"

            db.session.commit()

            print(new_code.current_code)
            sse.publish({"status": "new_code"}, type='updated_code')
    t2 = Timer(30, check_and_update_code)
    t2.start()


t = Timer(30, check_and_update_code)
t.start()
