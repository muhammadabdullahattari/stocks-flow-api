       
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):

    try:
        supabase_service.auth.sign_out(access_token=current_user.id)
        logger.info(f"User logged out: {current_user.id}")
        
    except Exception as e:
        logger.warning(f"Supabase logout failed (non-critical): {str(e)}")
    
    try:
        from app.models.sessions import UserSession
        
        db.query(UserSession).filter(UserSession.user_id == current_user.id).delete()
        db.commit()
        logger.info(f"Local sessions cleared for user: {current_user.id}")
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.warning(f"Failed to clear local sessions: {str(e)}")


@router.post("/logout-all-devices", status_code=status.HTTP_204_NO_CONTENT)
def logout_all_devices(current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):

    try:
        supabase_service.auth.sign_out(scope="all", access_token=current_user.id)
        logger.info(f"User logged out from all devices: {current_user.id}")
        
    except Exception as e:
        logger.warning(f"Supabase logout-all failed (non-critical): {str(e)}")
    
    try:
        from app.models.sessions import UserSession
        
        db.query(UserSession).filter(
            UserSession.user_id == current_user.id
        ).delete()
        db.commit()
        logger.info(f"All local sessions cleared for user: {current_user.id}")
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.warning(f"Failed to clear all sessions: {str(e)}")
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
