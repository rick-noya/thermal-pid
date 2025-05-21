# persistence package 
import os
from .local import LocalRepository

def get_repo():
    if os.getenv("USE_SUPABASE"):
        try:
            from .supabase import SupabaseRepository
            return SupabaseRepository()
        except ImportError:
            print("SupabaseRepository not implemented yet, falling back to LocalRepository.")
    return LocalRepository() 